from uuid import UUID

from cognitive_os.infrastructure.ai.openai_answer import ChatDecision
from cognitive_os.workers.recording_index import run_index_once
from test_recording_knowledge import Embeddings, approve
from test_recordings import prepare_report, storage, video_file


class Answering:
    decision = ChatDecision(can_answer=True, answer="Respuesta de prueba", source_index=0)

    def __init__(self, *args):
        pass

    def answer(self, question, fragments):
        return self.decision

    def close(self):
        pass


class Declining(Answering):
    decision = ChatDecision(can_answer=False)


def index_org(api, owner, storage):
    _, recording_id, report = prepare_report(api, owner, storage)
    approve(api, owner, recording_id, report["revision"])
    assert api.post(f"/api/v1/recordings/{recording_id}/index", headers=owner["headers"]).status_code == 202
    assert run_index_once(api.app.state.engine, Embeddings(), UUID(owner["organization_id"]))
    return recording_id


def test_ask_answers_with_citation_when_confident(api, account, storage, monkeypatch):
    owner = account()
    recording_id = index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Answering)
    response = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                        json={"question": "Como se hace el formulario?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gap_detected"] is False
    assert body["answer"] == "Respuesta de prueba"
    assert body["citation"]["recording_id"] == recording_id
    assert api.get("/api/v1/chatbot/gaps", headers=owner["headers"]).json() == []


def test_ask_records_and_dedupes_gap_when_not_confident(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Declining)

    response = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                        json={"question": "Pregunta sin respaldo"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gap_detected"] is True and body["gap"]["asked_count"] == 1
    gap_id = body["gap"]["id"]

    # Rephrasing the same unanswered question increments the same gap instead of creating another.
    response2 = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                         json={"question": "Otra forma de preguntar lo mismo"})
    assert response2.json()["gap"]["id"] == gap_id
    assert response2.json()["gap"]["asked_count"] == 2

    gaps = api.get("/api/v1/chatbot/gaps", headers=owner["headers"]).json()
    assert len(gaps) == 1 and gaps[0]["id"] == gap_id

    outsider = account()
    assert api.get("/api/v1/chatbot/gaps", headers=outsider["headers"]).json() == []
    assert api.post(f"/api/v1/chatbot/gaps/{gap_id}/resolve", headers=outsider["headers"]).status_code == 404

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.post(f"/api/v1/chatbot/gaps/{gap_id}/resolve", headers=reader["headers"]).status_code == 403

    resolved = api.post(f"/api/v1/chatbot/gaps/{gap_id}/resolve", headers=owner["headers"])
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    assert api.get("/api/v1/chatbot/gaps", headers=owner["headers"]).json() == []


def test_ask_records_gap_when_no_indexed_content(api, account, monkeypatch):
    owner = account()
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)
    response = api.post("/api/v1/chatbot/ask", headers=owner["headers"], json={"question": "Cualquier cosa"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gap_detected"] is True
    assert body["gap"]["best_score"] is None


def test_chat_history_lists_recent_questions_tenant_scoped(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Answering)
    assert api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                    json={"question": "Como se hace el formulario?"}).status_code == 200

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Declining)
    assert api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                    json={"question": "Pregunta sin respaldo"}).status_code == 200

    history = api.get("/api/v1/chatbot/history", headers=owner["headers"]).json()
    assert len(history) == 2
    assert history[0]["question"] == "Pregunta sin respaldo" and history[0]["answered"] is False
    assert history[1]["answered"] is True

    outsider = account()
    assert api.get("/api/v1/chatbot/history", headers=outsider["headers"]).json() == []
