from uuid import UUID

from sqlalchemy.orm import Session

from cognitive_os.infrastructure.database.models import User
from test_chatbot import Answering, index_org
from test_policies import policy_storage, upload_and_index
from test_recording_knowledge import Embeddings
from test_recordings import storage, video_file


def make_platform_staff(api, user):
    with Session(api.app.state.engine) as db, db.begin():
        db.get(User, UUID(user["id"])).is_platform_staff = True


def test_master_requires_platform_staff_flag(api, account):
    owner = account()
    assert api.get("/api/v1/master/organizations", headers=owner["headers"]).status_code == 403
    assert api.get("/api/v1/master/usage", headers=owner["headers"]).status_code == 403
    assert api.post("/api/v1/master/chatbot/ask", headers=owner["headers"],
                    json={"question": "Algo"}).status_code == 403


def test_master_lists_organizations_and_compares_usage(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Answering)
    asked = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                     json={"question": "Como se hace el formulario?"})
    assert asked.status_code == 200, asked.text

    staff = account()
    make_platform_staff(api, staff)

    orgs = api.get("/api/v1/master/organizations", headers=staff["headers"]).json()
    assert any(o["id"] == owner["organization_id"] for o in orgs)

    usage = api.get("/api/v1/master/usage", headers=staff["headers"]).json()
    entry = next(e for e in usage if e["organization_id"] == owner["organization_id"])
    assert entry["answered"] == 1 and entry["questions"] == 1


def test_master_chatbot_ask_compares_across_organizations(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    staff = account()
    make_platform_staff(api, staff)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.master.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.master.OpenAIAnswerProvider", Answering)

    response = api.post("/api/v1/master/chatbot/ask", headers=staff["headers"],
                        json={"question": "Como se hace el formulario?"})
    assert response.status_code == 200, response.text
    entries = response.json()
    entry = next(e for e in entries if e["organization_id"] == owner["organization_id"])
    assert entry["answer"] == "Respuesta de prueba"

    # Master mode never writes into a client's own usage log.
    usage = api.get("/api/v1/usage/summary", headers=owner["headers"]).json()
    assert usage["questions"] == 0


def test_master_policies_ask_compares_across_organizations(api, account, policy_storage, monkeypatch):
    owner = account()
    upload_and_index(api, owner)
    other_org = account()
    staff = account()
    make_platform_staff(api, staff)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.master.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.master.OpenAIAnswerProvider", Answering)

    response = api.post("/api/v1/master/policies/ask", headers=staff["headers"],
                        json={"question": "Cual es el deducible?"})
    assert response.status_code == 200, response.text
    entries = response.json()
    entry = next(e for e in entries if e["organization_id"] == owner["organization_id"])
    assert entry["answer"] == "Respuesta de prueba"
    empty_entry = next(e for e in entries if e["organization_id"] == other_org["organization_id"])
    assert empty_entry["answer"] is None
