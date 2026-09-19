"""Natural-language change proposals against a published procedure version.
Applying one never edits the published version: it clones its steps into a
brand new draft version, splices in the proposed step, and copies each
cloned step's evidence links so the usual submit/approve gate still passes.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select

from cognitive_os.application.procedures import get_procedure, get_version, version_steps
from cognitive_os.application.sessions import require_author
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import (
    AuditEvent, ChangeProposal, ProcedureVersion, Step, StepEvidence, StepRecordingEvidence, Tutorial,
)


def _get_proposal(db, member, proposal_id, *, lock=False):
    query = select(ChangeProposal).where(ChangeProposal.id == proposal_id,
                                         ChangeProposal.organization_id == member.organization_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise ApplicationError(404, "Change proposal not found")
    return item


def propose_change(db, member, version_id, request_text, provider):
    require_author(member)
    version = get_version(db, member, version_id)
    if version.status != "published":
        raise ApplicationError(409, "Only a published version can receive change proposals")
    steps = version_steps(db, member, version_id)
    decision = provider.propose([{"position": s.position, "instruction": s.instruction,
                                  "expected_result": s.expected_result} for s in steps], request_text)
    if not decision.can_propose:
        raise ApplicationError(422, "Could not derive a clear step change from that request")
    if decision.kind == "insert":
        if decision.after_position > len(steps):
            raise ApplicationError(422, "Could not derive a clear step insertion from that request")
    elif decision.step_position is None or not any(s.position == decision.step_position for s in steps):
        raise ApplicationError(422, "Could not find the step that request refers to")
    proposal = ChangeProposal(organization_id=member.organization_id, version_id=version_id,
                              procedure_id=version.procedure_id, requested_by=member.user_id,
                              request_text=request_text, kind=decision.kind,
                              after_position=decision.after_position, step_position=decision.step_position,
                              instruction=decision.instruction, expected_result=decision.expected_result,
                              rationale=decision.rationale, model_name=provider.model_name)
    db.add(proposal)
    db.commit()
    return proposal


def list_proposals(db, member, version_id, status="pending"):
    get_version(db, member, version_id)
    return db.scalars(select(ChangeProposal).where(
        ChangeProposal.organization_id == member.organization_id,
        ChangeProposal.version_id == version_id, ChangeProposal.status == status,
    ).order_by(ChangeProposal.created_at.desc())).all()


def discard_proposal(db, member, proposal_id):
    require_author(member)
    proposal = _get_proposal(db, member, proposal_id, lock=True)
    if proposal.status != "pending":
        raise ApplicationError(409, "Only a pending proposal can be discarded")
    proposal.status = "discarded"
    proposal.resolved_at = datetime.now(UTC)
    proposal.resolved_by = member.user_id
    db.commit()
    return proposal


def apply_proposal(db, member, proposal_id):
    require_author(member)
    proposal = _get_proposal(db, member, proposal_id, lock=True)
    if proposal.status != "pending":
        raise ApplicationError(409, "Only a pending proposal can be applied")
    source_version = get_version(db, member, proposal.version_id, lock=True)
    procedure = get_procedure(db, member, proposal.procedure_id, lock=True)
    source_steps = version_steps(db, member, proposal.version_id)
    number = db.scalar(select(func.max(ProcedureVersion.version_number)).where(
        ProcedureVersion.organization_id == member.organization_id,
        ProcedureVersion.procedure_id == procedure.id)) or 0
    new_version = ProcedureVersion(organization_id=member.organization_id, procedure_id=procedure.id,
                                   source_session_id=source_version.source_session_id,
                                   version_number=number + 1, status="draft",
                                   summary=source_version.summary, model_name=proposal.model_name,
                                   prompt_version="change-proposal-v1")
    db.add(new_version)
    db.flush()

    if proposal.kind == "insert":
        ordered = [("new", None)] if proposal.after_position == 0 else []
        for step in source_steps:
            ordered.append(("existing", step))
            if step.position == proposal.after_position:
                ordered.append(("new", None))
    elif proposal.kind == "delete":
        ordered = [("existing", step) for step in source_steps if step.position != proposal.step_position]
        if len(ordered) == len(source_steps):
            raise ApplicationError(409, "Target step no longer exists in this version")
        if not ordered:
            raise ApplicationError(409, "Cannot delete the only step of a procedure")
    else:  # edit
        ordered = [("existing", step) for step in source_steps]
        if not any(step.position == proposal.step_position for _, step in ordered):
            raise ApplicationError(409, "Target step no longer exists in this version")

    step_id_map = {}
    for position, (kind, step) in enumerate(ordered, 1):
        if kind == "existing":
            editing = proposal.kind == "edit" and step.position == proposal.step_position
            new_step = Step(organization_id=member.organization_id, version_id=new_version.id,
                            position=position,
                            instruction=proposal.instruction if editing else step.instruction,
                            expected_result=proposal.expected_result if editing else step.expected_result,
                            origin="user_explained" if editing else step.origin,
                            validation_status="confirmed" if editing else step.validation_status)
            db.add(new_step)
            db.flush()
            step_id_map[step.id] = new_step.id
        else:
            db.add(Step(organization_id=member.organization_id, version_id=new_version.id,
                       position=position, instruction=proposal.instruction,
                       expected_result=proposal.expected_result, origin="user_explained",
                       validation_status="confirmed"))

    for old_id, new_id in step_id_map.items():
        for evidence in db.scalars(select(StepEvidence).where(
                StepEvidence.organization_id == member.organization_id, StepEvidence.step_id == old_id)):
            db.add(StepEvidence(organization_id=member.organization_id, step_id=new_id,
                                evidence_id=evidence.evidence_id, explanation=evidence.explanation))
        recording_evidence = db.scalar(select(StepRecordingEvidence).where(
            StepRecordingEvidence.organization_id == member.organization_id,
            StepRecordingEvidence.step_id == old_id))
        if recording_evidence:
            db.add(StepRecordingEvidence(organization_id=member.organization_id, step_id=new_id,
                                         recording_id=recording_evidence.recording_id,
                                         report_revision=recording_evidence.report_revision,
                                         frame_indices=recording_evidence.frame_indices))

    tutorial = db.scalar(select(Tutorial).where(Tutorial.organization_id == member.organization_id,
                                               Tutorial.version_id == proposal.version_id, Tutorial.format == "markdown"))
    if tutorial:
        db.add(Tutorial(organization_id=member.organization_id, version_id=new_version.id,
                        format="markdown", content=tutorial.content))

    proposal.status = "applied"
    proposal.applied_version_id = new_version.id
    proposal.resolved_at = datetime.now(UTC)
    proposal.resolved_by = member.user_id
    db.add(AuditEvent(organization_id=member.organization_id, actor_id=member.user_id,
                      action="change_proposal.applied", resource_type="procedure_version",
                      resource_id=new_version.id, details={"proposal_id": str(proposal.id)}))
    db.commit()
    return new_version
