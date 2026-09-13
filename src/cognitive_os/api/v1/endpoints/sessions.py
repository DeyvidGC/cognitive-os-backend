from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from cognitive_os.api.dependencies import Db, CaptureMember as Member
from cognitive_os.application import sessions
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Job, LearningSession, SessionEvent
from cognitive_os.schemas.sessions import EventCreate, EventResponse, JobResponse, SessionCreate, SessionResponse

router = APIRouter(tags=["learning-sessions"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/learning-sessions", response_model=SessionResponse, status_code=201)
def create_session(data: SessionCreate, db: Db, member: Member):
    return sessions.create_session(db, member, data)


@router.get("/learning-sessions", response_model=list[SessionResponse])
def list_sessions(db: Db, member: Member, limit: Limit = 20, offset: Offset = 0):
    return db.scalars(select(LearningSession).where(
        LearningSession.organization_id == member.organization_id
    ).order_by(LearningSession.created_at.desc(), LearningSession.id).limit(limit).offset(offset)).all()


@router.get("/learning-sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, db: Db, member: Member):
    return sessions.get_session(db, member, session_id)


@router.post("/learning-sessions/{session_id}/events", response_model=EventResponse)
def add_event(session_id: UUID, data: EventCreate, db: Db, member: Member):
    return sessions.add_event(db, member, session_id, data)


@router.get("/learning-sessions/{session_id}/events", response_model=list[EventResponse])
def list_events(session_id: UUID, db: Db, member: Member, limit: Limit = 50, offset: Offset = 0):
    sessions.get_session(db, member, session_id)
    return db.scalars(select(SessionEvent).where(
        SessionEvent.organization_id == member.organization_id,
        SessionEvent.session_id == session_id
    ).order_by(SessionEvent.sequence_number).limit(limit).offset(offset)).all()


@router.post("/learning-sessions/{session_id}/finish", response_model=JobResponse, status_code=202)
def finish_session(session_id: UUID, db: Db, member: Member):
    return sessions.finish_session(db, member, session_id)


@router.get("/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
def get_job(job_id: UUID, db: Db, member: Member):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == member.organization_id))
    if job is None:
        raise ApplicationError(404, "Job not found")
    return job
