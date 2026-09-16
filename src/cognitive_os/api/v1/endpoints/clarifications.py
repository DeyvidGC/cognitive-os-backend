from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application.sessions import get_session, require_session_writer
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Clarification, Recording, RecordingReport
from cognitive_os.schemas.evidence import ClarificationAnswer, ClarificationCreate, ClarificationResponse

router = APIRouter(tags=["clarifications"])


def require_questions_open(db, member, session):
    if session.status == "capturing":
        return
    report = db.scalar(select(RecordingReport).join(Recording,
        Recording.id == RecordingReport.recording_id).where(
            Recording.session_id == session.id, Recording.organization_id == member.organization_id,
            RecordingReport.organization_id == member.organization_id))
    if session.status != "completed" or report is None or report.review_status == "approved":
        raise ApplicationError(409, "Questions are closed while processing or after approval")


@router.post("/learning-sessions/{session_id}/clarifications", response_model=ClarificationResponse, status_code=201)
def create_clarification(session_id: UUID, data: ClarificationCreate, db: Db, member: Member):
    session = get_session(db, member, session_id, for_update=True)
    require_questions_open(db, member, session)
    item = Clarification(organization_id=member.organization_id, session_id=session_id, question=data.question)
    db.add(item)
    db.commit()
    return item


@router.get("/learning-sessions/{session_id}/clarifications", response_model=list[ClarificationResponse])
def list_clarifications(session_id: UUID, db: Db, member: Member):
    get_session(db, member, session_id)
    return db.scalars(select(Clarification).where(Clarification.organization_id == member.organization_id,
                                                 Clarification.session_id == session_id).order_by(Clarification.created_at)).all()


@router.put("/learning-sessions/{session_id}/clarifications/{clarification_id}/answer", response_model=ClarificationResponse)
def answer_clarification(session_id: UUID, clarification_id: UUID, data: ClarificationAnswer, db: Db, member: Member):
    session = get_session(db, member, session_id, for_update=True)
    require_session_writer(member, session)
    require_questions_open(db, member, session)
    item = db.scalar(select(Clarification).where(Clarification.organization_id == member.organization_id,
                                                Clarification.session_id == session_id, Clarification.id == clarification_id))
    if item is None:
        raise ApplicationError(404, "Clarification not found")
    item.answer = data.answer
    item.answered_by = member.user_id
    item.resolved_at = datetime.now(UTC)
    db.commit()
    return item
