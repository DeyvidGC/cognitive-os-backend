from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import select, or_, and_

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application import recordings
from cognitive_os.application.sessions import finish_session, get_session
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Job, Recording, ReportRevision, RecordingReport, LearningSession
from cognitive_os.infrastructure.storage.azure_recordings import recording_store
from cognitive_os.schemas.recordings import (
    RecordingCreate, RecordingResponse, ReportEdit, ReportRegenerate, ReportResponse, ReportReview, SignedTransfer,
)
from cognitive_os.schemas.procedures import VersionResponse
from cognitive_os.schemas.sessions import JobResponse, SessionResponse

router = APIRouter(tags=["recordings"])


@router.get("/recordings/capabilities")
def capabilities(request: Request, member: Member):
    settings = request.app.state.settings
    workers = request.app.state.workers
    return {"media_types": ["video/webm", "video/mp4"],
            "max_bytes": settings.recording_max_bytes, "max_seconds": settings.recording_max_seconds,
            "frame_interval_seconds": settings.recording_frame_interval_seconds,
            "storage_configured": bool(settings.azure_storage_connection_string),
            "ai_configured": bool(settings.openai_api_key),
            "worker_mode": "embedded" if settings.embedded_workers else "external",
            "local_workers": workers.status() if workers else {},
            "model": settings.openai_model, "analysis_mode": "sampled_frames_after_upload",
            "audio_supported": True, "audio_consent_required": True, "max_recordings_per_session": 1,
            "duration_scope": "session", "history_available": True,
            "proactive_questions": True, "observation_interval_seconds": max(15, settings.agent_min_interval_seconds),
            "live_observation": "websocket_snapshots", "resumable_uploads": True,
            "transcription_model": settings.openai_transcription_model}


@router.get("/recordings")
def history(db: Db, member: Member, cursor: UUID | None = None,
            limit: int = Query(25, ge=1, le=100), procedure_id: UUID | None = None,
            status: str | None = Query(None, max_length=30), query: str = Query("", max_length=200)):
    statement = select(Recording, LearningSession, RecordingReport).join(LearningSession,
        and_(LearningSession.id == Recording.session_id,
             LearningSession.organization_id == Recording.organization_id)).outerjoin(RecordingReport,
        and_(RecordingReport.recording_id == Recording.id,
             RecordingReport.organization_id == Recording.organization_id)).where(
        Recording.organization_id == member.organization_id)
    if procedure_id:
        statement = statement.where(LearningSession.procedure_id == procedure_id)
    if status:
        statement = statement.where(Recording.status == status)
    if query.strip():
        statement = statement.where(or_(LearningSession.objective.icontains(query.strip(), autoescape=True),
            LearningSession.application_name.icontains(query.strip(), autoescape=True),
            Recording.title.icontains(query.strip(), autoescape=True)))
    if cursor:
        anchor = recordings.get_recording(db, member, cursor)
        statement = statement.where(or_(Recording.created_at < anchor.created_at,
            and_(Recording.created_at == anchor.created_at, Recording.id < anchor.id)))
    rows = db.execute(statement.order_by(Recording.created_at.desc(), Recording.id.desc()).limit(limit + 1)).all()
    return {"items": [{**RecordingResponse.model_validate(video).model_dump(mode="json"),
                       "session": SessionResponse.model_validate(session).model_dump(mode="json"),
                       "procedure_id": session.procedure_id,
                       "duration_ms": report.sampling.get("duration_ms") if report else None,
                       "revision": report.revision if report else None,
                       "review_status": report.review_status if report else None}
                      for video, session, report in rows[:limit]],
            "next_cursor": str(rows[limit - 1][0].id) if len(rows) > limit else None}


@router.post("/learning-sessions/{session_id}/recordings", response_model=RecordingResponse, status_code=201)
def create(session_id: UUID, data: RecordingCreate, request: Request, db: Db, member: Member):
    return recordings.create_recording(db, member, session_id, data, request.app.state.settings)


@router.get("/learning-sessions/{session_id}/recordings", response_model=list[RecordingResponse])
def list_recordings(session_id: UUID, db: Db, member: Member):
    get_session(db, member, session_id)
    return db.scalars(select(Recording).where(Recording.organization_id == member.organization_id,
                                               Recording.session_id == session_id)).all()


@router.get("/recordings/{recording_id}", response_model=RecordingResponse)
def get(recording_id: UUID, db: Db, member: Member):
    return recordings.get_recording(db, member, recording_id)


@router.post("/recordings/{recording_id}/upload-url", response_model=SignedTransfer)
def upload_url(recording_id: UUID, request: Request, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id, lock=True)
    recordings.require_recording_writer(db, member, item)
    if item.status != "uploading":
        raise ApplicationError(409, "Recording is already uploaded")
    with recording_store(request.app.state.settings) as store:
        return store.transfer(item, write=True)


@router.post("/recordings/{recording_id}/complete", response_model=RecordingResponse)
def complete(recording_id: UUID, request: Request, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id, lock=True)
    recordings.require_recording_writer(db, member, item)
    if item.status != "uploading":
        return item
    with recording_store(request.app.state.settings) as store:
        item.blob_snapshot = store.freeze(item)
    item.status = "uploaded"
    item.uploaded_at = datetime.now(UTC)
    db.commit()
    return item


@router.post("/recordings/{recording_id}/process", response_model=JobResponse, status_code=202)
def process(recording_id: UUID, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id)
    return finish_session(db, member, item.session_id)


@router.post("/recordings/{recording_id}/retry", response_model=JobResponse, status_code=202)
def retry(recording_id: UUID, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id)
    recordings.require_recording_writer(db, member, item)
    job = db.scalar(select(Job).where(Job.organization_id == member.organization_id,
                                      Job.recording_id == recording_id, Job.kind == "analyze_recording").with_for_update())
    if job is None or job.status != "failed":
        raise ApplicationError(409, "Only failed recording jobs can be retried")
    session = get_session(db, member, item.session_id, for_update=True)
    item = recordings.get_recording(db, member, recording_id, lock=True)
    job.status = "pending"
    job.stage, job.progress_percent = "queued", 0
    job.attempts = 0
    job.available_at = datetime.now(UTC)
    job.completed_at = job.last_error = job.locked_by = job.locked_until = None
    item.status, item.error_code, session.status = "queued", None, "processing"
    db.commit()
    return job


@router.get("/recordings/{recording_id}/playback", response_model=SignedTransfer)
def playback(recording_id: UUID, request: Request, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id)
    if not item.blob_snapshot:
        raise ApplicationError(409, "Upload is not complete")
    with recording_store(request.app.state.settings) as store:
        return store.transfer(item)


@router.get("/recordings/{recording_id}/report", response_model=ReportResponse)
def report(recording_id: UUID, db: Db, member: Member):
    return recordings.get_report(db, member, recording_id)


@router.put("/recordings/{recording_id}/report", response_model=ReportResponse)
def edit_report(recording_id: UUID, data: ReportEdit, db: Db, member: Member):
    return recordings.update_report(db, member, recording_id, data)


@router.post("/recordings/{recording_id}/report/review", response_model=ReportResponse)
def review_report(recording_id: UUID, data: ReportReview, request: Request, db: Db, member: Member):
    return recordings.update_report(db, member, recording_id, data, review=True,
                                    embedding_model=request.app.state.settings.openai_embedding_model)


@router.post("/recordings/{recording_id}/report/regenerate", response_model=JobResponse, status_code=202)
def regenerate_report(recording_id: UUID, data: ReportRegenerate, db: Db, member: Member):
    return recordings.regenerate(db, member, recording_id, data.revision)


@router.post("/recordings/{recording_id}/procedure", response_model=VersionResponse, status_code=201)
def convert_report(recording_id: UUID, db: Db, member: Member):
    return recordings.convert_to_procedure(db, member, recording_id)


@router.get("/recordings/{recording_id}/upload-status")
def upload_status(recording_id: UUID, request: Request, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id)
    recordings.require_recording_writer(db, member, item)
    if item.status != "uploading":
        return {"recording_id": str(item.id), "complete": True, "blocks": []}
    with recording_store(request.app.state.settings) as store:
        return {"complete": False, **store.upload_status(item)}


@router.post("/recordings/{recording_id}/commit-blocks", response_model=RecordingResponse)
def commit_blocks(recording_id: UUID, request: Request, db: Db, member: Member):
    item = recordings.get_recording(db, member, recording_id, lock=True)
    recordings.require_recording_writer(db, member, item)
    if item.status != "uploading":
        return item
    with recording_store(request.app.state.settings) as store:
        item.blob_snapshot = store.commit_blocks(item)
    item.status, item.uploaded_at = "uploaded", datetime.now(UTC)
    db.commit()
    return item


@router.get("/recordings/{recording_id}/report/history")
def report_history(recording_id: UUID, db: Db, member: Member,
                   limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    recordings.get_recording(db, member, recording_id)
    items = db.scalars(select(ReportRevision).where(ReportRevision.recording_id == recording_id,
        ReportRevision.organization_id == member.organization_id).order_by(ReportRevision.revision.desc()).limit(limit).offset(offset))
    return [{"revision": item.revision, "snapshot": item.snapshot, "created_at": item.created_at} for item in items]


@router.get("/recordings/{recording_id}/transcript")
def transcript(recording_id: UUID, db: Db, member: Member):
    report = recordings.get_report(db, member, recording_id)
    return {"recording_id": recording_id, "revision": report.revision,
            "text": report.sampling.get("transcript", ""),
            "audio_present": report.sampling.get("audio_present", False),
            "analyzed": report.sampling.get("audio_analyzed", False),
            "model": report.sampling.get("transcription_model"),
            "exclusion_reason": report.sampling.get("audio_exclusion_reason")}
