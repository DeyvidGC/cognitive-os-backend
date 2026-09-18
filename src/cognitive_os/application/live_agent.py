import base64
from datetime import UTC, datetime, timedelta
import hashlib
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cognitive_os.application.auth import authenticate
from cognitive_os.application.sessions import get_session, require_session_writer
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import (
    AgentTurn, Membership, Clarification, RealtimeVoiceSession, SessionEvent,
)


def authorize(db, token, organization_id, session_id):
    auth = authenticate(db, token)
    member = db.get(Membership, (organization_id, auth.user_id))
    if not member:
        raise ApplicationError(403, "Organization access denied")
    session = get_session(db, member, session_id, for_update=True)
    require_session_writer(member, session)
    if session.status != "capturing":
        raise ApplicationError(409, "Live observation requires a capturing session")
    return member, session


def normalize_frame(value):
    if not value:
        return None
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) > 512000:
            raise ValueError("Frame too large")
        with Image.open(BytesIO(raw)) as image:
            if image.format not in {"JPEG", "PNG"} or image.width * image.height > 2073600:
                raise ValueError("Invalid frame")
            image.load()
            image = image.convert("RGB")
            image.thumbnail((1280, 720))
            output = BytesIO()
            image.save(output, format="JPEG", quality=75)
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except Exception:
        raise ApplicationError(422, "Invalid screenshot; send a small JPEG or PNG as raw base64") from None


def gate_and_persist_clarification(db, organization_id, session_id, question, offset_ms):
    """Insert a new Clarification unless one is already open or it repeats a known question.

    Shared by the turn-based reply path (handle_turn) and the realtime voice
    path, so both enforce the same "one open question at a time" policy.
    """
    question = question.strip()[:4000]
    if not question:
        return None
    existing = db.scalars(select(Clarification).where(
        Clarification.organization_id == organization_id, Clarification.session_id == session_id)).all()
    if any(item.resolved_at is None for item in existing):
        return None
    if question.casefold() in {item.question.strip().casefold() for item in existing}:
        return None
    created = Clarification(organization_id=organization_id, session_id=session_id, question=question)
    db.add(created)
    db.flush()
    return created


def start_voice_session(engine, token, organization_id, session_id, settings):
    """Authorize and register a new realtime voice session.

    Returns (voice_session_id, objective, next_sequence_number). The partial
    unique index on realtime_voice_sessions(status='active') is what actually
    enforces "one active session per LearningSession"; the concurrency count
    below only bounds total OpenAI Realtime spend across all sessions.
    """
    with Session(engine) as db:
        member, session = authorize(db, token, organization_id, session_id)
        active = db.scalar(select(func.count()).select_from(RealtimeVoiceSession).where(
            RealtimeVoiceSession.status == "active"))
        if active is not None and active >= settings.realtime_max_concurrent_sessions:
            raise ApplicationError(429, "Too many concurrent live voice sessions")
        voice_session = RealtimeVoiceSession(organization_id=organization_id, session_id=session_id,
                                             user_id=member.user_id, model=settings.openai_realtime_model,
                                             started_at=datetime.now(UTC))
        db.add(voice_session)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ApplicationError(409, "A live voice session is already active for this session") from exc
        next_sequence = db.scalar(select(func.max(SessionEvent.sequence_number)).where(
            SessionEvent.organization_id == organization_id, SessionEvent.session_id == session_id))
        return voice_session.id, session.objective, (next_sequence + 1 if next_sequence is not None else 0)


def end_voice_session(engine, voice_session_id, ended_reason):
    with Session(engine) as db:
        item = db.get(RealtimeVoiceSession, voice_session_id, with_for_update=True)
        if item is not None and item.status == "active":
            item.status = "failed" if ended_reason == "error" else "ended"
            item.ended_reason = ended_reason
            item.ended_at = datetime.now(UTC)
            db.commit()


def append_voice_transcript(engine, organization_id, session_id, voice_session_id,
                            sequence_number, speaker, text, offset_ms):
    """Persist one voice transcript segment as a backend-authored SessionEvent.

    Uses a dedicated event_type (realtime_voice_transcript) so it never mixes
    with the 'transcript' events a client can already submit, which the
    analyze_recording worker folds into a different context key.
    """
    text = text.strip()[:5000]
    if not text:
        return
    with Session(engine) as db:
        event = SessionEvent(organization_id=organization_id, session_id=session_id,
                             sequence_number=sequence_number,
                             idempotency_key=f"realtime-voice:{voice_session_id}:{sequence_number}",
                             event_type="realtime_voice_transcript",
                             offset_ms=max(0, offset_ms), payload={"text": text, "speaker": speaker})
        db.add(event)
        voice_session = db.get(RealtimeVoiceSession, voice_session_id, with_for_update=True)
        if voice_session is not None:
            voice_session.transcript_event_count = (voice_session.transcript_event_count or 0) + 1
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


def check_live_status(engine, token, organization_id, session_id):
    """Re-run the same authorization/status checks as a turn, discarding the result.

    Used by the voice session's periodic reauth timer so a revoked token or a
    session that stopped capturing ends the call promptly, without locking the
    LearningSession row on every audio chunk in between.
    """
    with Session(engine) as db:
        authorize(db, token, organization_id, session_id)


def resolve_clarification(engine, token, organization_id, session_id, clarification_id, text):
    text = text.strip()
    if not text:
        raise ApplicationError(422, "A clarification answer requires text")
    with Session(engine) as db:
        member, _ = authorize(db, token, organization_id, session_id)
        question = db.scalar(select(Clarification).where(
            Clarification.id == clarification_id, Clarification.organization_id == organization_id,
            Clarification.session_id == session_id).with_for_update())
        if question is None:
            raise ApplicationError(404, "Clarification not found")
        if question.resolved_at and question.answer != text:
            raise ApplicationError(409, "Clarification was already answered")
        question.answer = text
        question.answered_by, question.resolved_at = member.user_id, datetime.now(UTC)
        db.commit()


def create_voice_clarification(engine, organization_id, session_id, question, offset_ms):
    with Session(engine) as db, db.begin():
        created = gate_and_persist_clarification(db, organization_id, session_id, question, offset_ms)
        if created is None:
            return None
        return {"id": str(created.id), "question": created.question}


def handle_turn(engine, token, organization_id, session_id, data, settings, provider):
    image = normalize_frame(data.image_base64)
    digest = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    now = datetime.now(UTC)
    with Session(engine, expire_on_commit=False) as db:
        member, session = authorize(db, token, organization_id, session_id)
        if data.clarification_id:
            question = db.scalar(select(Clarification).where(
                Clarification.id == data.clarification_id,
                Clarification.organization_id == organization_id,
                Clarification.session_id == session_id))
            if question is None:
                raise ApplicationError(404, "Clarification not found")
            if not data.text.strip():
                raise ApplicationError(422, "A clarification answer requires text")
        turn = db.scalar(select(AgentTurn).where(AgentTurn.organization_id == organization_id,
            AgentTurn.session_id == session_id, AgentTurn.client_message_id == data.message_id))
        if turn:
            if turn.request_hash != digest or turn.user_id != member.user_id:
                raise ApplicationError(409, "Message ID already used with different input")
            if turn.status == "completed":
                return {"type": "reply", "message_id": str(data.message_id), "reply": turn.response}
            if turn.status == "pending" and turn.locked_until > now:
                raise ApplicationError(409, "Agent is still processing this message")
            if turn.attempts >= 3:
                raise ApplicationError(429, "Agent message retry limit reached")
        else:
            count = db.scalar(select(func.count()).select_from(AgentTurn).where(
                AgentTurn.organization_id == organization_id, AgentTurn.session_id == session_id))
            if count >= settings.agent_max_turns_per_session:
                raise ApplicationError(429, "Session agent message limit reached")
            turn = AgentTurn(organization_id=organization_id, session_id=session_id,
                             user_id=member.user_id, client_message_id=data.message_id,
                             request_hash=digest, user_text=data.text)
            db.add(turn)
        with db.no_autoflush:
            last = db.scalar(select(AgentTurn).where(AgentTurn.organization_id == organization_id,
                AgentTurn.session_id == session_id, AgentTurn.id != turn.id if turn.id else True
            ).order_by(AgentTurn.created_at.desc()).limit(1))
            if last and ((last.status == "pending" and last.locked_until > now)
                         or (now - last.created_at).total_seconds() < settings.agent_min_interval_seconds):
                raise ApplicationError(429, "Wait before sending another observation")
            history = db.scalars(select(AgentTurn).where(AgentTurn.organization_id == organization_id,
                AgentTurn.session_id == session_id, AgentTurn.status == "completed"
            ).order_by(AgentTurn.created_at.desc()).limit(10)).all()
        attempt = uuid4()
        turn.attempts = (turn.attempts or 0) + 1
        turn.attempt_id, turn.status, turn.locked_until = attempt, "pending", now + timedelta(seconds=120)
        objective = session.objective
        history_data = [{"user": h.user_text, "assistant": h.response} for h in reversed(history)]
        questions = db.scalars(select(Clarification).where(
            Clarification.organization_id == organization_id,
            Clarification.session_id == session_id)).all()
        history_data += [{"question": q.question, "answer": q.answer} for q in questions[-100:]]
        db.commit()
        turn_id = turn.id
    try:
        reply = provider.respond(objective, data.text, image, history_data).model_dump(mode="json")
        with Session(engine) as db:
            # Recheck token/session after the model call, before making the reply visible.
            member, _ = authorize(db, token, organization_id, session_id)
            turn = db.get(AgentTurn, turn_id, with_for_update=True)
            if turn.attempt_id != attempt or turn.locked_until <= datetime.now(UTC):
                raise ApplicationError(409, "Agent request expired; resend the message")
            if data.clarification_id:
                question = db.get(Clarification, data.clarification_id, with_for_update=True)
                if question.resolved_at and question.answer != data.text.strip():
                    raise ApplicationError(409, "Clarification was already answered")
                question.answer = data.text.strip()
                question.answered_by, question.resolved_at = member.user_id, datetime.now(UTC)
            # The session lock serializes persistence across simultaneous sockets.
            reply["clarifications"] = []
            proposed = reply["questions"]
            reply["questions"] = []
            for text in proposed:
                created = gate_and_persist_clarification(db, organization_id, session_id, text, data.offset_ms)
                if created:
                    reply["questions"] = [created.question]
                    reply["clarifications"] = [{"type": "clarification.created", "event_id": str(created.id),
                        "clarification_id": str(created.id), "question": created.question,
                        "offset_ms": data.offset_ms}]
                    break
            turn.response, turn.status = reply, "completed"
            db.commit()
        return {"type": "reply", "message_id": str(data.message_id), "reply": reply}
    except Exception:
        with Session(engine) as db:
            turn = db.get(AgentTurn, turn_id, with_for_update=True)
            if turn and turn.attempt_id == attempt and turn.status == "pending":
                turn.status = "failed"
                db.commit()
        raise
