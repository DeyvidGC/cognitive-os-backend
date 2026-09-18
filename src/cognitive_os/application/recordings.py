from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from cognitive_os.application.sessions import get_session, require_session_writer
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import (
    AuditEvent, Clarification, Job, Procedure, ProcedureVersion, Recording, RecordingReport,
    ReportRevision, Step, StepRecordingEvidence, Tutorial,
)
from cognitive_os.schemas.recordings import ReportResponse, VisualReportContent


def get_recording(db, member, recording_id, *, lock=False):
    query = select(Recording).where(Recording.id == recording_id,
                                     Recording.organization_id == member.organization_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise ApplicationError(404, "Recording not found")
    return item


def create_recording(db, member, session_id, data, settings):
    session = get_session(db, member, session_id, for_update=True)
    require_session_writer(member, session)
    existing = db.scalar(select(Recording).where(
        Recording.organization_id == member.organization_id, Recording.session_id == session_id))
    if existing:
        if (existing.idempotency_key, existing.media_type, existing.size_bytes, existing.content_sha256, existing.audio_consent) != (
                str(data.idempotency_key), data.media_type, data.size_bytes, data.content_sha256, data.audio_consent):
            raise ApplicationError(409, "This session already has a different recording")
        return existing
    if session.status != "capturing":
        raise ApplicationError(409, "Session is no longer capturing")
    if data.size_bytes > settings.recording_max_bytes:
        raise ApplicationError(413, "Recording exceeds size limit")
    recording_id = uuid4()
    extension = "webm" if data.media_type == "video/webm" else "mp4"
    item = Recording(id=recording_id, organization_id=member.organization_id, session_id=session_id,
                     idempotency_key=str(data.idempotency_key), media_type=data.media_type,
                     size_bytes=data.size_bytes, content_sha256=data.content_sha256,
                     audio_consent=data.audio_consent, consent_at=datetime.now(UTC),
                     blob_key=f"{member.organization_id}/{session_id}/{recording_id}.{extension}")
    db.add(item)
    db.commit()
    return item


def require_recording_writer(db, member, item):
    require_session_writer(member, get_session(db, member, item.session_id))


def get_report(db, member, recording_id, *, lock=False):
    get_recording(db, member, recording_id)
    query = select(RecordingReport).where(RecordingReport.recording_id == recording_id,
                                            RecordingReport.organization_id == member.organization_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise ApplicationError(404, "Recording report is not ready")
    return item


def validate_sources(content, sampling):
    count = len(sampling["frames"])
    statements = [*content.instructions, *content.prerequisites, *content.business_rules, *content.exceptions]
    if any(index < 0 or index >= count for step in statements for index in step.frame_indices):
        raise ApplicationError(422, "Report references an unknown sampled frame")
    available = set(sampling.get("text_sources", []))
    for step in statements:
        if not step.frame_indices and not step.text_sources:
            raise ApplicationError(422, "Every instruction requires supporting sources")
        if not set(step.text_sources).issubset(available):
            raise ApplicationError(422, "Report references unavailable textual sources")


def archive_report(db, report):
    db.add(ReportRevision(recording_id=report.recording_id, organization_id=report.organization_id,
                          revision=report.revision,
                          snapshot={**ReportResponse.model_validate(report).model_dump(mode="json"),
                                    "original_content": report.original_content}))


def update_report(db, member, recording_id, data, *, review=False, embedding_model=None):
    recording = get_recording(db, member, recording_id)
    get_session(db, member, recording.session_id, for_update=True)
    db.refresh(recording)
    if recording.status != "ready":
        raise ApplicationError(409, "Wait for recording analysis to finish")
    if member.role != "reviewer":
        require_recording_writer(db, member, recording)
    report = get_report(db, member, recording_id, lock=True)
    if report.revision != data.revision:
        raise ApplicationError(409, "Report changed; reload the latest revision")
    if report.review_status == "approved":
        raise ApplicationError(409, "Approved report is immutable")
    archive_report(db, report)
    if review:
        unresolved = db.scalar(select(Clarification.id).where(
            Clarification.organization_id == member.organization_id,
            Clarification.session_id == recording.session_id, Clarification.resolved_at.is_(None)).limit(1))
        if data.decision == "approved" and unresolved:
            raise ApplicationError(409, "Resolve pending clarifications before approving the report")
        report.review_status = data.decision
        report.reviewer_id = member.user_id
        report.reviewed_at = datetime.now(UTC)
        report.feedback = data.feedback
    else:
        validate_sources(data.content, report.sampling)
        report.content = data.content.model_dump(mode="json")
        report.review_status = "pending"
        report.reviewer_id = report.reviewed_at = report.feedback = None
    report.revision += 1
    if report.review_status == "approved" and embedding_model:
        from cognitive_os.application.recording_knowledge import enqueue_index
        enqueue_index(db, recording, report, embedding_model)
    db.add(AuditEvent(organization_id=member.organization_id, actor_id=member.user_id,
                      action="recording.report_reviewed" if review else "recording.report_edited",
                      resource_type="recording", resource_id=recording_id,
                      details={"revision": report.revision, "review_status": report.review_status}))
    db.commit()
    return report


def regenerate(db, member, recording_id, revision):
    recording = get_recording(db, member, recording_id)
    require_recording_writer(db, member, recording)
    job = db.scalar(select(Job).where(Job.organization_id == member.organization_id,
                                      Job.recording_id == recording_id, Job.kind == "analyze_recording").with_for_update())
    session = get_session(db, member, recording.session_id, for_update=True)
    report = get_report(db, member, recording_id, lock=True)
    if report.revision != revision or report.review_status == "approved":
        raise ApplicationError(409, "Report revision changed or report is approved")
    if job is not None and job.status in {"pending", "running"}:
        return job
    if job is None or recording.status not in {"ready", "failed"}:
        raise ApplicationError(409, "Recording cannot be regenerated")
    if db.scalar(select(Clarification.id).where(Clarification.organization_id == member.organization_id,
        Clarification.session_id == session.id, Clarification.resolved_at.is_(None)).limit(1)):
        raise ApplicationError(409, "Resolve pending clarifications before regenerating")
    job.status, job.attempts = "pending", 0
    job.stage, job.progress_percent = "queued", 0
    job.available_at = datetime.now(UTC)
    job.completed_at = job.locked_by = job.locked_until = job.last_error = None
    recording.status, recording.error_code, session.status = "queued", None, "processing"
    db.commit()
    return job


def convert_to_procedure(db, member, recording_id):
    recording = get_recording(db, member, recording_id)
    require_recording_writer(db, member, recording)
    report = get_report(db, member, recording_id, lock=True)
    if report.review_status != "approved" or recording.status != "ready":
        raise ApplicationError(409, "Approve the recording report before conversion")
    if report.version_id:
        return db.get(ProcedureVersion, report.version_id)
    content = VisualReportContent.model_validate(report.content)
    if not content.instructions:
        raise ApplicationError(409, "Report needs instructions before conversion")
    session = get_session(db, member, recording.session_id)
    procedure = Procedure(organization_id=member.organization_id, title=content.title, scope=session.objective)
    db.add(procedure)
    db.flush()
    version = ProcedureVersion(organization_id=member.organization_id, procedure_id=procedure.id,
                               source_session_id=session.id, version_number=1, status="draft",
                               summary=content.summary, model_name=report.model_name, prompt_version=report.prompt_version)
    db.add(version)
    db.flush()
    tutorial = [f"# {content.title}", content.summary, content.report]
    for heading, facts in (("Requisitos previos", content.prerequisites),
                           ("Reglas de negocio", content.business_rules), ("Excepciones", content.exceptions)):
        if facts:
            tutorial.append("## " + heading + "\n" + "\n".join("- " + fact.text for fact in facts))
    for position, instruction in enumerate(content.instructions, 1):
        step = Step(organization_id=member.organization_id, version_id=version.id, position=position,
                    instruction=instruction.instruction, expected_result=instruction.expected_result,
                    origin="observed" if instruction.frame_indices else "user_explained",
                    validation_status="confirmed")
        db.add(step)
        db.flush()
        db.add(StepRecordingEvidence(organization_id=member.organization_id, step_id=step.id,
                                     recording_id=recording.id, report_revision=report.revision,
                                     frame_indices=instruction.frame_indices))
        tutorial.append(f"## {position}. Paso\n{instruction.instruction}\n\n{instruction.expected_result}")
        for alternative in instruction.alternatives:
            target = f"paso {alternative.target_step}" if alternative.target_step else "fin"
            tutorial.append(f"- {alternative.condition}: {target}")
    db.add(Tutorial(organization_id=member.organization_id, version_id=version.id,
                    format="markdown", content="\n\n".join(tutorial)))
    report.version_id = version.id
    db.add(AuditEvent(organization_id=member.organization_id, actor_id=member.user_id,
                      action="recording.converted", resource_type="procedure_version", resource_id=version.id,
                      details={"recording_id": str(recording.id), "report_revision": report.revision}))
    db.commit()
    return version
