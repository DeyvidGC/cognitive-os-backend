import asyncio
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application.live_agent import authorize, handle_turn
from cognitive_os.application.sessions import get_session
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_live import OpenAILiveProvider
from cognitive_os.infrastructure.database.models import AgentTurn, Job
from cognitive_os.schemas.agent import AgentAuth, AgentInput
from cognitive_os.schemas.sessions import JobResponse

router = APIRouter(tags=["agent"])


@router.get("/learning-sessions/{session_id}/jobs", response_model=list[JobResponse])
def session_jobs(session_id: UUID, db: Db, member: Member,
                 limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    get_session(db, member, session_id)
    return db.scalars(select(Job).where(Job.organization_id == member.organization_id,
        Job.session_id == session_id).order_by(Job.created_at.desc(), Job.id).limit(limit).offset(offset)).all()


@router.get("/learning-sessions/{session_id}/agent/messages")
def messages(session_id: UUID, db: Db, member: Member,
             limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    get_session(db, member, session_id)
    turns = db.scalars(select(AgentTurn).where(AgentTurn.organization_id == member.organization_id,
        AgentTurn.session_id == session_id).order_by(AgentTurn.created_at, AgentTurn.id).limit(limit).offset(offset))
    return [{"id": t.id, "message_id": t.client_message_id, "text": t.user_text,
             "reply": t.response, "status": t.status, "created_at": t.created_at} for t in turns]


@router.websocket("/learning-sessions/{session_id}/agent/live")
async def live(session_id: UUID, socket: WebSocket):
    settings = socket.app.state.settings
    origin = socket.headers.get("origin")
    same_host = {f"http://{socket.headers.get('host')}", f"https://{socket.headers.get('host')}"}
    if origin and origin not in set(settings.cors_origins) | same_host:
        await socket.close(code=1008)
        return
    await socket.accept()
    provider = None
    try:
        raw = await asyncio.wait_for(socket.receive_text(), timeout=15)
        if len(raw) > 16000:
            raise ApplicationError(422, "Authentication message too large")
        auth = AgentAuth.model_validate_json(raw)
        engine = socket.app.state.engine
        if engine is None:
            raise ApplicationError(503, "Database is not configured")
        def check_auth():
            with Session(engine) as db:
                authorize(db, auth.token, auth.organization_id, session_id)
        await asyncio.to_thread(check_auth)
        provider = OpenAILiveProvider(settings)
        await socket.send_json({"type": "ready", "model": settings.openai_model,
                                "protocol_version": 2, "proactive_questions": True,
                                "observation_interval_seconds": max(15, settings.agent_min_interval_seconds),
                                "audio_input": False, "audio_output": False,
                                "mode": "snapshot_conversation", "min_interval_seconds": settings.agent_min_interval_seconds})
        while True:
            raw = await asyncio.wait_for(socket.receive_text(), timeout=300)
            if len(raw) > 750000:
                raise ApplicationError(413, "Agent message too large")
            try:
                data = AgentInput.model_validate_json(raw)
                await socket.send_json({"type": "processing", "message_id": str(data.message_id)})
                result = await asyncio.to_thread(handle_turn, engine, auth.token, auth.organization_id,
                                                 session_id, data, settings, provider)
                await socket.send_json(result)
            except ApplicationError as exc:
                await socket.send_json({"type": "error", "status": exc.status_code, "detail": exc.detail})
                if exc.status_code in {401, 403}:
                    break
            except ValidationError:
                await socket.send_json({"type": "error", "status": 422, "detail": "Invalid agent input"})
            except Exception:
                await socket.send_json({"type": "error", "status": 503, "detail": "Agent provider unavailable"})
    except WebSocketDisconnect:
        return
    except ApplicationError as exc:
        await socket.send_json({"type": "error", "status": exc.status_code, "detail": exc.detail})
    except (ValidationError, ValueError, asyncio.TimeoutError):
        await socket.send_json({"type": "error", "status": 503, "detail": "Agent authentication or configuration unavailable"})
    finally:
        if provider:
            provider.close()
        try:
            await socket.close()
        except RuntimeError:
            pass
