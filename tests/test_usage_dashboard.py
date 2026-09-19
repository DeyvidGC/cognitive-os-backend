from uuid import UUID

from test_chatbot import Answering, Declining, index_org
from test_recording_knowledge import Embeddings
from test_recordings import storage, video_file


def test_usage_summary_counts_answers_and_gaps(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Answering)
    answered = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                        json={"question": "Como se hace el formulario?"})
    assert answered.status_code == 200, answered.text

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Declining)
    gap = api.post("/api/v1/chatbot/ask", headers=owner["headers"], json={"question": "Pregunta sin respaldo"})
    assert gap.status_code == 200, gap.text

    response = api.get("/api/v1/usage/summary", headers=owner["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["questions"] == 2
    assert body["answered"] == 1
    assert body["coverage"] == 0.5
    assert body["answered_today"] == 1
    assert body["open_gaps"] == 1
    assert sum(day["total"] for day in body["per_day"]) == 2
    assert body["top_questions"][0]["total"] == 1

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.get("/api/v1/usage/summary", headers=reader["headers"]).status_code == 403

    outsider = account()
    empty = api.get("/api/v1/usage/summary", headers=outsider["headers"]).json()
    assert empty["questions"] == 0 and empty["coverage"] is None
