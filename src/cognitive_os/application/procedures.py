from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cognitive_os.application.sessions import get_session, require_author
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import (
    AuditEvent, KnowledgeChunk, Membership, Procedure, ProcedureVersion, Step, StepEvidence, Tutorial,
)
from cognitive_os.schemas.procedures import ProcedureCreate, StepWrite, VersionCreate


def audit(db: Session, member: Membership, action: str, version: ProcedureVersion):
    db.add(AuditEvent(organization_id=member.organization_id, actor_id=member.user_id,
                      action=action, resource_type="procedure_version", resource_id=version.id))


def require_reviewer(member: Membership):
    if member.role not in {"owner", "reviewer"}:
        raise ApplicationError(403, "Reviewer role required")


def get_procedure(db: Session, member: Membership, procedure_id: UUID, *, lock=False) -> Procedure:
    query = select(Procedure).where(Procedure.id == procedure_id,
                                    Procedure.organization_id == member.organization_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise ApplicationError(404, "Procedure not found")
    return item


def get_version(db: Session, member: Membership, version_id: UUID, *, lock=False) -> ProcedureVersion:
    query = select(ProcedureVersion).where(ProcedureVersion.id == version_id,
                                           ProcedureVersion.organization_id == member.organization_id)
    version = db.scalar(query.with_for_update() if lock else query)
    if version is None or (member.role == "reader" and version.status != "published"):
        raise ApplicationError(404, "Version not found")
    return version


def create_procedure(db: Session, member: Membership, data: ProcedureCreate) -> Procedure:
    require_author(member)
    item = Procedure(organization_id=member.organization_id, **data.model_dump())
    db.add(item)
    db.commit()
    return item


def create_version(db: Session, member: Membership, procedure_id: UUID, data: VersionCreate) -> ProcedureVersion:
    require_author(member)
    get_procedure(db, member, procedure_id, lock=True)
    if data.source_session_id:
        get_session(db, member, data.source_session_id)
    number = db.scalar(select(func.max(ProcedureVersion.version_number)).where(
        ProcedureVersion.organization_id == member.organization_id,
        ProcedureVersion.procedure_id == procedure_id)) or 0
    version = ProcedureVersion(organization_id=member.organization_id, procedure_id=procedure_id,
                               version_number=number + 1, **data.model_dump())
    db.add(version)
    db.flush()
    audit(db, member, "version.created", version)
    db.commit()
    return version


def write_step(db: Session, member: Membership, version_id: UUID, data: StepWrite,
               step_id: UUID | None = None) -> Step:
    require_author(member)
    version = get_version(db, member, version_id, lock=True)
    if version.status != "draft":
        raise ApplicationError(409, "Only draft versions can be edited")
    if step_id:
        step = db.scalar(select(Step).where(Step.id == step_id, Step.version_id == version_id,
                                            Step.organization_id == member.organization_id))
        if step is None:
            raise ApplicationError(404, "Step not found")
        for key, value in data.model_dump().items():
            setattr(step, key, value)
    else:
        step = Step(organization_id=member.organization_id, version_id=version_id, **data.model_dump())
        db.add(step)
    audit(db, member, "step.updated" if step_id else "step.created", version)
    db.commit()
    return step


def version_steps(db: Session, member: Membership, version_id: UUID) -> list[Step]:
    get_version(db, member, version_id)
    return list(db.scalars(select(Step).where(Step.version_id == version_id,
                                             Step.organization_id == member.organization_id).order_by(Step.position)))


def transition(db: Session, member: Membership, version_id: UUID, action: str) -> ProcedureVersion:
    if action in {"approve", "return", "retire"}:
        require_reviewer(member)
    else:
        require_author(member)
    version = get_version(db, member, version_id, lock=True)
    source, target = {"submit": ("draft", "in_review"), "approve": ("in_review", "approved"),
                      "return": ("in_review", "draft"), "retire": ("published", "retired")}[action]
    if version.status != source:
        raise ApplicationError(409, f"Version must be {source}")
    if action in {"submit", "approve"}:
        tutorial = db.scalar(select(Tutorial.id).where(
            Tutorial.organization_id == member.organization_id,
            Tutorial.version_id == version_id, Tutorial.format == "markdown"))
        if tutorial is None:
            raise ApplicationError(409, "Create a Markdown tutorial before review")
        steps = version_steps(db, member, version_id)
        if not steps or any(s.validation_status != "confirmed" for s in steps):
            raise ApplicationError(409, "All steps must be confirmed before review and approval")
        if [s.position for s in steps] != list(range(1, len(steps) + 1)):
            raise ApplicationError(409, "Step positions must be consecutive starting at 1")
        for step in steps:
            if step.origin in {"observed", "inferred"} and not db.scalar(select(StepEvidence.evidence_id).where(
                StepEvidence.organization_id == member.organization_id, StepEvidence.step_id == step.id).limit(1)):
                raise ApplicationError(409, "Observed and inferred steps require supporting evidence")
    version.status = target
    if action == "approve":
        version.reviewer_id = member.user_id
        version.approved_at = datetime.now(UTC)
    audit(db, member, f"version.{action}", version)
    db.commit()
    return version


def write_tutorial(db: Session, member: Membership, version_id: UUID, content: str) -> Tutorial:
    require_author(member)
    version = get_version(db, member, version_id, lock=True)
    if version.status != "draft":
        raise ApplicationError(409, "Only draft tutorials can be edited; create a new version")
    tutorial = db.scalar(select(Tutorial).where(Tutorial.organization_id == member.organization_id,
                                               Tutorial.version_id == version_id, Tutorial.format == "markdown"))
    if tutorial is None:
        tutorial = Tutorial(organization_id=member.organization_id, version_id=version_id, format="markdown")
        db.add(tutorial)
    tutorial.content = content
    audit(db, member, "tutorial.updated", version)
    db.commit()
    return tutorial


def publish(db: Session, member: Membership, version_id: UUID) -> ProcedureVersion:
    require_reviewer(member)
    version = get_version(db, member, version_id)
    # Serialize publications by procedure, then refresh the version after acquiring the lock.
    get_procedure(db, member, version.procedure_id, lock=True)
    db.refresh(version, with_for_update=True)
    if version.status == "published":
        return version
    if version.status != "approved":
        raise ApplicationError(409, "Version must be approved")
    tutorial = db.scalar(select(Tutorial).where(Tutorial.organization_id == member.organization_id,
                                               Tutorial.version_id == version_id, Tutorial.format == "markdown"))
    if tutorial is None or not tutorial.content:
        raise ApplicationError(409, "A reviewed Markdown tutorial is required; create it before submitting")
    previous = db.scalars(select(ProcedureVersion).where(
        ProcedureVersion.organization_id == member.organization_id,
        ProcedureVersion.procedure_id == version.procedure_id,
        ProcedureVersion.status == "published").with_for_update()).all()
    for item in previous:
        item.status = "retired"
        audit(db, member, "version.superseded", item)
    db.flush()
    for step in version_steps(db, member, version_id):
        db.add(KnowledgeChunk(organization_id=member.organization_id, version_id=version_id,
                              step_id=step.id, position=step.position,
                              content=f"{step.instruction}\n{step.expected_result}"))
    version.status = "published"
    version.published_at = datetime.now(UTC)
    audit(db, member, "version.published", version)
    db.commit()
    return version
