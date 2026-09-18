from uuid import UUID

from fastapi import APIRouter, Request, Response
from typing import Literal
from openai import OpenAIError
from pydantic import BaseModel, Field
from sqlalchemy import text

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application.recording_knowledge import enqueue_index, report_flow, search_vectors
from cognitive_os.application.recordings import get_recording, get_report, require_recording_writer
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
from cognitive_os.schemas.sessions import JobResponse
from cognitive_os.application.bpmn import report_bpmn
from cognitive_os.application.report_exports import export_snapshot, export_document
from cognitive_os.infrastructure.report_documents import MEDIA_TYPES

router = APIRouter(tags=["recording-knowledge"])


class SemanticQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1200)
    limit: int = Field(default=5, ge=1, le=20)


@router.get("/recordings/{recording_id}/flow")
def flow(recording_id: UUID, db: Db, member: Member):
    return report_flow(get_report(db, member, recording_id))


@router.get("/recordings/{recording_id}/flow/bpmn")
def bpmn(recording_id: UUID, db: Db, member: Member):
    report = get_report(db, member, recording_id)
    if not report.content.get("instructions"):
        raise ApplicationError(409, "Report has no activities to export")
    return {"xml": report_bpmn(report), "revision": report.revision,
            "review_status": report.review_status, "recording_id": recording_id}


class DocumentExport(BaseModel):
    revision: int = Field(ge=1)
    format: Literal["docx", "pdf"] = "pdf"
    style: Literal["tutorial", "report"] = "tutorial"


@router.post("/recordings/{recording_id}/report/file", response_class=Response,
             responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}}
                                          for mime in MEDIA_TYPES.values()}}})
def document(recording_id: UUID, data: DocumentExport, request: Request, db: Db, member: Member):
    snapshot, source = export_snapshot(db, member, recording_id, data.revision)
    payload = export_document(snapshot, source, request.app.state.settings, format=data.format, style=data.style)
    name = f"{data.style}-{recording_id}-r{data.revision}.{data.format}"
    return Response(payload, media_type=MEDIA_TYPES[data.format], headers={
        "Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.post("/recordings/{recording_id}/index", response_model=JobResponse, status_code=202)
def index(recording_id: UUID, request: Request, db: Db, member: Member):
    item = get_recording(db, member, recording_id, lock=True)
    require_recording_writer(db, member, item)
    report = get_report(db, member, recording_id)
    job = enqueue_index(db, item, report, request.app.state.settings.openai_embedding_model, retry=True)
    db.commit()
    return job


@router.get("/recordings/{recording_id}/index")
def index_status(recording_id: UUID, request: Request, db: Db, member: Member):
    report = get_report(db, member, recording_id)
    model = request.app.state.settings.openai_embedding_model
    count = db.scalar(text("SELECT count(*) FROM cognitive.recording_vectors WHERE organization_id=:org "
                           "AND recording_id=:recording AND report_revision=:revision AND model_name=:model"),
                      {"org": member.organization_id, "recording": recording_id,
                       "revision": report.revision, "model": model})
    return {"recording_id": recording_id, "revision": report.revision, "model": model,
            "dimensions": 1536, "chunks": count, "indexed": bool(count) and report.review_status == "approved"}


@router.post("/recordings/search")
def search(data: SemanticQuery, request: Request, db: Db, member: Member):
    if not data.query.strip():
        raise ApplicationError(422, "Query cannot be blank")
    provider = None
    try:
        provider = OpenAIEmbeddingProvider(request.app.state.settings)
        # Release the read transaction before a potentially slow provider request.
        organization_id = member.organization_id
        db.rollback()
        vector = provider.embed([data.query])[0]
        return {"model": provider.model_name,
                "results": search_vectors(db, organization_id, provider.model_name, vector, data.limit)}
    except (ValueError, OpenAIError):
        raise ApplicationError(503, "Semantic search provider unavailable or not configured") from None
    finally:
        if provider:
            provider.close()
