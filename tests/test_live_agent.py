import base64
from io import BytesIO
import json
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from cognitive_os.infrastructure.database.models import Clarification
from cognitive_os.schemas.agent import AgentReply


class FakeAgent:
    calls = 0
    def __init__(self, settings):
        pass
    def respond(self, objective, text, image, history):
        type(self).calls += 1
        return AgentReply(observation="Formulario visible", answer="Que dato vas a introducir?", questions=[])
    def close(self):
        pass


def session(api, owner):
    return api.post("/api/v1/learning-sessions", headers=owner["headers"], json={
        "objective": "Demostracion", "application_name": "Demo", "consent": True}).json()["id"]


def test_live_agent_auth_reply_idempotency_and_history(api, account, monkeypatch):
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.agent.OpenAILiveProvider", FakeAgent)
    owner = account()
    session_id = session(api, owner)
    FakeAgent.calls = 0
    with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live") as ws:
        ws.send_json({"type": "auth", "token": owner["token"], "organization_id": owner["organization_id"], "consent": True})
        assert ws.receive_json()["type"] == "ready"
        message = {"type": "message", "message_id": str(uuid4()), "text": "Voy a introducir el nombre"}
        for _ in range(2):
            ws.send_json(message)
            assert ws.receive_json()["type"] == "processing"
            assert ws.receive_json()["reply"]["observation"] == "Formulario visible"
        assert FakeAgent.calls == 1
        message["text"] = "Changed"
        ws.send_json(message)
        ws.receive_json()
        assert ws.receive_json()["status"] == 409
    history = api.get(f"/api/v1/learning-sessions/{session_id}/agent/messages", headers=owner["headers"]).json()
    assert len(history) == 1 and history[0]["status"] == "completed"
    outsider = account()
    assert api.get(f"/api/v1/learning-sessions/{session_id}/agent/messages", headers=outsider["headers"]).status_code == 404


def test_agent_rejects_unauthenticated_and_reader(api, account, monkeypatch):
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.agent.OpenAILiveProvider", FakeAgent)
    owner = account()
    reader = account(role="reader", organization_id=owner["organization_id"])
    session_id = session(api, owner)
    for token in ("invalid-token", reader["token"]):
        with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live") as ws:
            ws.send_json({"type": "auth", "token": token, "organization_id": owner["organization_id"], "consent": True})
            assert ws.receive_json()["type"] == "error"


def test_live_frame_validation():
    import pytest
    from cognitive_os.application.live_agent import normalize_frame
    from cognitive_os.domain.errors import ApplicationError
    with pytest.raises(ApplicationError):
        normalize_frame("not-base64")


class FakeRealtime:
    def __init__(self, settings):
        self.audio_chunks = []
        self.frames = []
        self.tool_results = []

    async def connect(self, objective):
        self.objective = objective

    async def push_audio_chunk(self, data):
        self.audio_chunks.append(data)

    async def push_frame(self, data_url):
        self.frames.append(data_url)

    async def submit_tool_result(self, call_id, accepted):
        self.tool_results.append((call_id, accepted))

    async def events(self):
        return
        yield  # pragma: no cover - makes this an async generator with no events

    async def close(self):
        pass


def test_live_voice_auth_ready_and_end(api, account, monkeypatch):
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.agent.OpenAIRealtimeSession", FakeRealtime)
    owner = account()
    session_id = session(api, owner)
    with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live-voice") as ws:
        ws.send_json({"type": "auth", "token": owner["token"], "organization_id": owner["organization_id"], "consent": True})
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["audio_input"] is True and ready["audio_output"] is True
        ws.send_json({"type": "end"})
        assert ws.receive_json() == {"type": "session.ending", "reason": "client_disconnect"}


def test_live_voice_rejects_unauthenticated_and_reader(api, account, monkeypatch):
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.agent.OpenAIRealtimeSession", FakeRealtime)
    owner = account()
    reader = account(role="reader", organization_id=owner["organization_id"])
    session_id = session(api, owner)
    for token in ("invalid-token", reader["token"]):
        with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live-voice") as ws:
            ws.send_json({"type": "auth", "token": token, "organization_id": owner["organization_id"], "consent": True})
            assert ws.receive_json()["type"] == "error"


def test_live_voice_rejects_second_concurrent_session(api, account, monkeypatch):
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.agent.OpenAIRealtimeSession", FakeRealtime)
    owner = account()
    session_id = session(api, owner)
    with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live-voice") as ws1:
        ws1.send_json({"type": "auth", "token": owner["token"], "organization_id": owner["organization_id"], "consent": True})
        assert ws1.receive_json()["type"] == "ready"
        with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live-voice") as ws2:
            ws2.send_json({"type": "auth", "token": owner["token"], "organization_id": owner["organization_id"], "consent": True})
            error = ws2.receive_json()
            assert error["type"] == "error" and error["status"] == 409
        ws1.send_json({"type": "end"})
        assert ws1.receive_json()["type"] == "session.ending"


class FakeRealtimeWithToolCall(FakeRealtime):
    async def events(self):
        yield {"type": "response.function_call_arguments.done", "call_id": "call-1",
               "name": "ask_clarifying_question",
               "arguments": json.dumps({"question": "Que campo debo llenar?"})}


def test_live_voice_forwards_audio_frame_and_creates_clarification(api, account, monkeypatch):
    created = {}

    def factory(settings):
        instance = FakeRealtimeWithToolCall(settings)
        created["instance"] = instance
        return instance

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.agent.OpenAIRealtimeSession", factory)
    owner = account()
    session_id = session(api, owner)
    buffer = BytesIO()
    Image.new("RGB", (4, 4), (10, 20, 30)).save(buffer, format="JPEG")
    image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    with api.websocket_connect(f"/api/v1/learning-sessions/{session_id}/agent/live-voice") as ws:
        ws.send_json({"type": "auth", "token": owner["token"], "organization_id": owner["organization_id"], "consent": True})
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(b"\x00\x01fake-pcm")
        ws.send_json({"type": "frame", "image_base64": image_base64})
        clarification_event = ws.receive_json()
        assert clarification_event["type"] == "clarification.created"
        assert clarification_event["question"] == "Que campo debo llenar?"
        ws.send_json({"type": "end"})
        assert ws.receive_json()["type"] == "session.ending"
    instance = created["instance"]
    assert instance.audio_chunks == [b"\x00\x01fake-pcm"]
    assert len(instance.frames) == 1
    assert instance.tool_results == [("call-1", True)]
    with Session(api.app.state.engine) as db:
        rows = db.scalars(select(Clarification).where(Clarification.session_id == UUID(session_id))).all()
        assert len(rows) == 1 and rows[0].question == "Que campo debo llenar?"
