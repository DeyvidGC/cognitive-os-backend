from test_chatbot import Answering, index_org
from test_recording_knowledge import Embeddings
from test_recordings import storage, video_file


def test_home_dashboard_reports_active_sessions_and_usage(api, account, storage, monkeypatch):
    owner = account()
    session = api.post("/api/v1/learning-sessions", headers=owner["headers"], json={
        "objective": "Registrar siniestro", "application_name": "Demo", "consent": True}).json()

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.get("/api/v1/dashboard/home", headers=reader["headers"]).status_code == 403

    home = api.get("/api/v1/dashboard/home", headers=owner["headers"]).json()
    assert home["open_gaps"] == 0 and home["answered_today"] == 0
    assert len(home["active_sessions"]) == 1
    active = home["active_sessions"][0]
    assert active["id"] == session["id"] and active["status"] == "capturing"
    assert active["author_name"] == "Test User"

    index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Answering)
    asked = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                     json={"question": "Como se hace el formulario?"})
    assert asked.status_code == 200, asked.text

    home_after = api.get("/api/v1/dashboard/home", headers=owner["headers"]).json()
    assert home_after["answered_today"] == 1
    reviewed = next(item for item in home_after["recent_activity"] if item["action"] == "recording.report_reviewed")
    assert reviewed["actor_name"] == "Test User"
    gap_events = [item for item in home_after["recent_activity"] if item["action"] == "chatbot.gap_detected"]
    assert gap_events == [], "the answered question above should not have created a gap"

    outsider = account()
    outsider_home = api.get("/api/v1/dashboard/home", headers=outsider["headers"]).json()
    assert outsider_home["active_sessions"] == [] and outsider_home["recent_activity"] == []
