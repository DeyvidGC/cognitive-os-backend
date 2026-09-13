from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from cognitive_os.application.procedures import audit, get_version
from cognitive_os.application.sessions import get_session, require_author, require_session_writer
from cognitive_os.core.config import Settings
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Evidence, Membership, Step, StepEvidence
from cognitive_os.infrastructure.storage.local import resolve_file, save_image
from cognitive_os.schemas.evidence import EvidenceLink


def upload(db: Session, member: Membership, session_id: UUID, file: BinaryIO,
           settings: Settings) -> Evidence:
    session = get_session(db, member, session_id, for_update=True)
    require_session_writer(member, session)
    if session.status != "capturing":
        raise ApplicationError(409, "Session is no longer capturing")
    key, media_type, sha256, size = save_image(settings.evidence_directory, file,
                                              f"{member.organization_id}/{session_id}", settings.max_evidence_bytes)
    evidence = Evidence(organization_id=member.organization_id, session_id=session_id,
                         storage_key=key, media_type=media_type, sha256=sha256,
                         size_bytes=size, captured_at=datetime.now(UTC))
    db.add(evidence)
    try:
        db.commit()
    except Exception:
        db.rollback()
        resolve_file(settings.evidence_directory, key).unlink(missing_ok=True)
        raise
    return evidence


def get_evidence(db: Session, member: Membership, evidence_id: UUID) -> Evidence:
    evidence = db.scalar(select(Evidence).where(Evidence.organization_id == member.organization_id,
                                               Evidence.id == evidence_id))
    if evidence is None:
        raise ApplicationError(404, "Evidence not found")
    return evidence


def link(db: Session, member: Membership, version_id: UUID, step_id: UUID, data: EvidenceLink):
    require_author(member)
    version = get_version(db, member, version_id, lock=True)
    if version.status != "draft":
        raise ApplicationError(409, "Only draft evidence links can be edited")
    step = db.scalar(select(Step).where(Step.id == step_id, Step.version_id == version_id,
                                       Step.organization_id == member.organization_id))
    if step is None:
        raise ApplicationError(404, "Step not found")
    evidence = get_evidence(db, member, data.evidence_id)
    if version.source_session_id and evidence.session_id != version.source_session_id:
        raise ApplicationError(409, "Evidence must belong to the source session")
    relation = db.get(StepEvidence, (member.organization_id, step_id, data.evidence_id))
    if relation is None:
        relation = StepEvidence(organization_id=member.organization_id, step_id=step_id,
                                evidence_id=data.evidence_id, explanation=data.explanation)
        db.add(relation)
    else:
        relation.explanation = data.explanation
    audit(db, member, "step.evidence_linked", version)
    db.commit()
    return evidence
