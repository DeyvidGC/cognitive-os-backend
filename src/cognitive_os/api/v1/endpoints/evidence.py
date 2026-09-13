from uuid import UUID

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application import evidence
from cognitive_os.application.sessions import get_session
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Evidence
from cognitive_os.infrastructure.storage.local import resolve_file
from cognitive_os.schemas.evidence import EvidenceLink, EvidenceResponse

router = APIRouter(tags=["evidence"])


@router.post("/learning-sessions/{session_id}/evidence", response_model=EvidenceResponse, status_code=201)
def upload_evidence(session_id: UUID, file: UploadFile, request: Request, db: Db, member: Member):
    return evidence.upload(db, member, session_id, file.file, request.app.state.settings)


@router.get("/learning-sessions/{session_id}/evidence", response_model=list[EvidenceResponse])
def list_evidence(session_id: UUID, db: Db, member: Member):
    get_session(db, member, session_id)
    return db.scalars(select(Evidence).where(Evidence.organization_id == member.organization_id,
                                            Evidence.session_id == session_id).order_by(Evidence.created_at)).all()


@router.get("/evidence/{evidence_id}/file")
def download_evidence(evidence_id: UUID, request: Request, db: Db, member: Member):
    item = evidence.get_evidence(db, member, evidence_id)
    path = resolve_file(request.app.state.settings.evidence_directory, item.storage_key)
    if not path.is_file():
        raise ApplicationError(404, "Evidence file not found")
    return FileResponse(path, media_type=item.media_type, filename=path.name,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.put("/procedure-versions/{version_id}/steps/{step_id}/evidence", response_model=EvidenceResponse)
def link_evidence(version_id: UUID, step_id: UUID, data: EvidenceLink, db: Db, member: Member):
    return evidence.link(db, member, version_id, step_id, data)
