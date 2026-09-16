import base64
from datetime import UTC, datetime, timedelta
import hashlib
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cognitive_os.application.auth import authenticate
from cognitive_os.application.sessions import get_session, require_session_writer
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import AgentTurn, Membership


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


def handle_turn(engine, token, organization_id, session_id, data, settings, provider):
    image = normalize_frame(data.image_base64)
    digest = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    now = datetime.now(UTC)
    with Session(engine, expire_on_commit=False) as db:
        member, session = authorize(db, token, organization_id, session_id)
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
        db.commit()
        turn_id = turn.id
    try:
        reply = provider.respond(objective, data.text, image, history_data).model_dump(mode="json")
        with Session(engine) as db:
            # Recheck token/session after the model call, before making the reply visible.
            authorize(db, token, organization_id, session_id)
            turn = db.get(AgentTurn, turn_id, with_for_update=True)
            if turn.attempt_id != attempt or turn.locked_until <= datetime.now(UTC):
                raise ApplicationError(409, "Agent request expired; resend the message")
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
