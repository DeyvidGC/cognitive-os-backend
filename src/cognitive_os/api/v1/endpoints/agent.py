import asyncio
import base64
import json
import logging
import time
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application.live_agent import (
    append_voice_transcript, authorize, check_live_status, create_voice_clarification,
    end_voice_session, handle_turn, normalize_frame, resolve_clarification, start_voice_session,
)
from cognitive_os.application.sessions import get_session
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_live import OpenAILiveProvider
from cognitive_os.infrastructure.ai.openai_realtime import OpenAIRealtimeSession
from cognitive_os.infrastructure.database.models import AgentTurn, Job
from cognitive_os.schemas.agent import AgentAuth, AgentInput, AgentVoiceInput
from cognitive_os.schemas.sessions import JobResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


class _VoiceSessionEnd(Exception):
    def __init__(self, reason: str):
        self.reason = reason


async def _safe_send(socket: WebSocket, payload: dict) -> None:
    try:
        await socket.send_json(payload)
    except Exception:
        pass


async def _voice_inbound(socket, realtime, engine, auth, session_id, settings, started_at):
    chunk_count = 0
    while True:
        message = await asyncio.wait_for(socket.receive(), timeout=300)
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        chunk = message.get("bytes")
        if chunk is not None:
            if len(chunk) > settings.realtime_audio_chunk_max_bytes:
                raise ApplicationError(413, "Audio chunk too large")
            before = time.monotonic()
            await realtime.push_audio_chunk(chunk)
            send_seconds = time.monotonic() - before
            if send_seconds > 0.5:
                logger.warning("Live voice session %s: forwarding a mic chunk to OpenAI took %.2fs "
                               "(t=%.1fs into the call)", session_id, send_seconds,
                               time.monotonic() - started_at)
            chunk_count += 1
            continue
        raw = message.get("text")
        if raw is None:
            continue
        if len(raw) > 750000:
            raise ApplicationError(413, "Agent message too large")
        data = AgentVoiceInput.model_validate_json(raw)
        if data.type == "frame":
            image = normalize_frame(data.image_base64)
            if image:
                logger.info("Live voice session %s: pushing a screenshot at t=%.1fs into the call "
                           "(%d mic chunks received so far)", session_id, time.monotonic() - started_at,
                           chunk_count)
                before = time.monotonic()
                await realtime.push_frame(image)
                push_seconds = time.monotonic() - before
                if push_seconds > 0.5:
                    logger.warning("Live voice session %s: pushing the screenshot to OpenAI took %.2fs",
                                   session_id, push_seconds)
        elif data.type == "clarification_answer":
            if not data.clarification_id:
                raise ApplicationError(422, "clarification_answer requires clarification_id")
            await asyncio.to_thread(resolve_clarification, engine, auth.token, auth.organization_id,
                                    session_id, data.clarification_id, data.text)
        elif data.type == "end":
            raise _VoiceSessionEnd("client_disconnect")


async def _voice_outbound(socket, realtime, engine, organization_id, session_id, voice_session_id, sequence,
                          started_at):
    # Transcript persistence is fire-and-forget: it must never delay forwarding the
    # next audio delta, or the client's playback buffer falls behind in real time.
    background: set[asyncio.Task] = set()
    last_event_at = time.monotonic()
    last_audio_delta_at = None
    audio_bytes_forwarded = 0

    def _log_background_failure(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("Voice transcript persistence failed for session %s", session_id, exc_info=exc)

    def _persist_transcript(speaker, transcript):
        task = asyncio.create_task(asyncio.to_thread(append_voice_transcript, engine, organization_id, session_id,
                                                      voice_session_id, sequence["value"], speaker, transcript, 0))
        sequence["value"] += 1
        background.add(task)
        task.add_done_callback(background.discard)
        task.add_done_callback(_log_background_failure)

    try:
        async for event in realtime.events():
            now = time.monotonic()
            provider_gap = now - last_event_at
            last_event_at = now
            if provider_gap > 3:
                logger.warning("Live voice session %s: %.2fs with no event at all from OpenAI before "
                               "receiving %s (t=%.1fs into the call) -- provider-side stall, not a "
                               "backend or network issue", session_id, provider_gap, event.get("type"),
                               now - started_at)
            kind = event.get("type")
            if kind == "response.output_audio.delta" and event.get("delta"):
                if last_audio_delta_at is not None:
                    delta_gap = now - last_audio_delta_at
                    if delta_gap > 1.5:
                        logger.warning("Live voice session %s: %.2fs gap between consecutive audio "
                                       "deltas from OpenAI (t=%.1fs into the call, %d bytes forwarded "
                                       "so far) -- OpenAI paused sending audio, backend just relayed "
                                       "what it had", session_id, delta_gap, now - started_at,
                                       audio_bytes_forwarded)
                last_audio_delta_at = now
                payload = base64.b64decode(event["delta"])
                audio_bytes_forwarded += len(payload)
                await socket.send_bytes(payload)
            elif kind == "conversation.item.input_audio_transcription.completed":
                _persist_transcript("user", event.get("transcript", ""))
            elif kind == "response.output_audio_transcript.done":
                _persist_transcript("assistant", event.get("transcript", ""))
            elif kind == "response.function_call_arguments.done" and event.get("name") == "ask_clarifying_question":
                try:
                    question = json.loads(event.get("arguments") or "{}").get("question", "")
                except (TypeError, ValueError):
                    question = ""
                created = await asyncio.to_thread(create_voice_clarification, engine, organization_id,
                                                  session_id, question, 0)
                await realtime.submit_tool_result(event.get("call_id", ""), accepted=created is not None)
                if created:
                    await socket.send_json({"type": "clarification.created", "clarification_id": created["id"],
                                            "question": created["question"]})
            elif kind == "error":
                # OpenAI's error payload can include free-text detail; log it for our own
                # debugging but never forward it to the client verbatim.
                logger.warning("Realtime provider reported an error event for session %s: %s",
                               session_id, event.get("error") or event)
                await socket.send_json({"type": "error", "status": 503,
                                        "detail": "Realtime provider reported an error"})
                # The call is no longer usable once the provider errors; end it now instead
                # of leaving the session idle until the client notices and disconnects.
                raise _VoiceSessionEnd("error")
    finally:
        if background:
            await asyncio.gather(*background, return_exceptions=True)


async def _voice_reauth(engine, token, organization_id, session_id, settings):
    while True:
        await asyncio.sleep(settings.realtime_reauth_interval_seconds)
        try:
            await asyncio.to_thread(check_live_status, engine, token, organization_id, session_id)
        except ApplicationError:
            raise _VoiceSessionEnd("session_status_changed")


async def _voice_ttl(max_seconds):
    await asyncio.sleep(max_seconds)
    raise _VoiceSessionEnd("max_duration")


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
        except (RuntimeError, WebSocketDisconnect):
            pass


@router.websocket("/learning-sessions/{session_id}/agent/live-voice")
async def live_voice(session_id: UUID, socket: WebSocket):
    """Bidirectional voice + periodic screenshots, bridged server-side to OpenAI Realtime.

    Distinct protocol from `live` above (binary audio frames, continuous streaming,
    server-pushed proactive questions), so `live` is left untouched for existing
    text/snapshot-only clients. See docs/seguimiento/endpoints/62-agent-live.md.
    """
    settings = socket.app.state.settings
    origin = socket.headers.get("origin")
    same_host = {f"http://{socket.headers.get('host')}", f"https://{socket.headers.get('host')}"}
    if origin and origin not in set(settings.cors_origins) | same_host:
        await socket.close(code=1008)
        return
    await socket.accept()
    engine = socket.app.state.engine
    realtime = None
    voice_session_id = None
    ended_reason = "client_disconnect"
    started_at = time.monotonic()
    try:
        raw = await asyncio.wait_for(socket.receive_text(), timeout=15)
        if len(raw) > 16000:
            raise ApplicationError(422, "Authentication message too large")
        auth = AgentAuth.model_validate_json(raw)
        if engine is None:
            raise ApplicationError(503, "Database is not configured")
        voice_session_id, objective, next_sequence = await asyncio.to_thread(
            start_voice_session, engine, auth.token, auth.organization_id, session_id, settings)
        realtime = OpenAIRealtimeSession(settings)
        await realtime.connect(objective)
        await socket.send_json({"type": "ready", "model": settings.openai_realtime_model,
                                "protocol_version": 1, "audio_input": True, "audio_output": True,
                                "proactive_questions": True,
                                "observation_interval_seconds": settings.observation_interval_seconds,
                                "session_max_seconds": settings.realtime_session_max_seconds})
        sequence = {"value": next_sequence}
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_voice_inbound(socket, realtime, engine, auth, session_id, settings, started_at))
                tg.create_task(_voice_outbound(socket, realtime, engine, auth.organization_id, session_id,
                                               voice_session_id, sequence, started_at))
                tg.create_task(_voice_reauth(engine, auth.token, auth.organization_id, session_id, settings))
                tg.create_task(_voice_ttl(settings.realtime_session_max_seconds))
        except* _VoiceSessionEnd as eg:
            ended_reason = eg.exceptions[0].reason
            await _safe_send(socket, {"type": "session.ending", "reason": ended_reason})
        except* WebSocketDisconnect:
            ended_reason = "client_disconnect"
        except* ApplicationError as eg:
            exc = eg.exceptions[0]
            ended_reason = "session_status_changed" if exc.status_code in {401, 403, 409} else "error"
            if exc.status_code not in {401, 403, 409}:
                logger.warning("Live voice session %s ended on ApplicationError %s: %s",
                               session_id, exc.status_code, exc.detail)
            await _safe_send(socket, {"type": "error", "status": exc.status_code, "detail": exc.detail})
        except* Exception as eg:
            ended_reason = "error"
            for exc in eg.exceptions:
                logger.exception("Live voice session %s crashed", session_id, exc_info=exc)
            await _safe_send(socket, {"type": "error", "status": 503, "detail": "Live voice session failed"})
    except WebSocketDisconnect:
        ended_reason = "client_disconnect"
    except ApplicationError as exc:
        ended_reason = "error"
        logger.warning("Live voice session %s failed to start (ApplicationError %s): %s",
                       session_id, exc.status_code, exc.detail)
        await _safe_send(socket, {"type": "error", "status": exc.status_code, "detail": exc.detail})
    except (ValidationError, ValueError, asyncio.TimeoutError) as exc:
        ended_reason = "error"
        logger.warning("Live voice session %s failed to start: %r", session_id, exc)
        await _safe_send(socket, {"type": "error", "status": 503,
                                  "detail": "Agent authentication or configuration unavailable"})
    except Exception:
        ended_reason = "error"
        logger.exception("Live voice session %s crashed before the task group started", session_id)
        await _safe_send(socket, {"type": "error", "status": 503, "detail": "Live voice session failed"})
    finally:
        logger.info("Live voice session %s ended after %.1fs, reason=%s",
                    session_id, time.monotonic() - started_at, ended_reason)
        if realtime is not None:
            await realtime.close()
        if voice_session_id is not None:
            await asyncio.to_thread(end_voice_session, engine, voice_session_id, ended_reason)
        try:
            await socket.close()
        except (RuntimeError, WebSocketDisconnect):
            pass
