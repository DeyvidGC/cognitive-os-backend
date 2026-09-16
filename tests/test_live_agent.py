from uuid import uuid4

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
