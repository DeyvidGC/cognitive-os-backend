from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Job, LearningSession, Membership, SessionEvent
from cognitive_os.schemas.sessions import EventCreate, SessionCreate


def require_author(member: Membership):
    if member.role not in {"owner", "author"}:
        raise ApplicationError(403, "Author role required")


def create_session(db: Session, member: Membership, data: SessionCreate) -> LearningSession:
    require_author(member)
    item = LearningSession(organization_id=member.organization_id, author_id=member.user_id,
                           objective=data.objective, application_name=data.application_name,
                           consent_at=datetime.now(UTC))
    db.add(item)
    db.commit()
    return item


def get_session(db: Session, member: Membership, session_id: UUID,
                *, for_update: bool = False) -> LearningSession:
    query = select(LearningSession).where(LearningSession.id == session_id,
                                          LearningSession.organization_id == member.organization_id)
    if for_update:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise ApplicationError(404, "Session not found")
    return item


def require_session_writer(member: Membership, item: LearningSession):
    require_author(member)
    if item.author_id != member.user_id and member.role != "owner":
        raise ApplicationError(403, "Only the author or organization owner can modify this session")


def add_event(db: Session, member: Membership, session_id: UUID, data: EventCreate) -> SessionEvent:
    item = get_session(db, member, session_id, for_update=True)
    require_session_writer(member, item)
    existing = db.scalar(select(SessionEvent).where(
        SessionEvent.organization_id == member.organization_id,
        SessionEvent.session_id == session_id,
        SessionEvent.idempotency_key == data.idempotency_key))
    payload = {"text": data.text}
    if existing:
        if (existing.sequence_number, existing.offset_ms, existing.event_type, existing.payload) != (
            data.sequence_number, data.offset_ms, data.event_type, payload
        ):
            raise ApplicationError(409, "Idempotency key already used with different content")
        return existing
    if item.status != "capturing":
        raise ApplicationError(409, "Session is no longer capturing")
    event = SessionEvent(organization_id=member.organization_id, session_id=session_id,
                         sequence_number=data.sequence_number, idempotency_key=data.idempotency_key,
                         event_type=data.event_type, offset_ms=data.offset_ms, payload=payload)
    db.add(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApplicationError(409, "Event sequence already exists") from exc
    return event


def finish_session(db: Session, member: Membership, session_id: UUID) -> Job:
    item = get_session(db, member, session_id, for_update=True)
    require_session_writer(member, item)
    key = f"consolidate:{session_id}"
    job = db.scalar(select(Job).where(Job.organization_id == member.organization_id,
                                      Job.idempotency_key == key))
    if job:
        return job
    if item.status != "capturing":
        raise ApplicationError(409, "Session cannot be finished in its current state")
    has_events = db.scalar(select(SessionEvent.id).where(
        SessionEvent.organization_id == member.organization_id,
        SessionEvent.session_id == session_id).limit(1))
    if has_events is None:
        raise ApplicationError(409, "Add at least one event before finishing")
    item.status = "processing"
    item.finished_at = datetime.now(UTC)
    job = Job(organization_id=member.organization_id, session_id=session_id,
              kind="consolidate", idempotency_key=key)
    db.add(job)
    # Session closure and durable work reservation must commit together.
    db.commit()
    return job
