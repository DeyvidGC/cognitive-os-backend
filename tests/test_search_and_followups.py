from uuid import UUID

from cognitive_os.workers.recording_index import run_index_once
from test_chatbot import Answering, index_org
from test_policies import policy_storage, upload_and_index
from test_procedures import draft, ready
from test_recording_knowledge import Embeddings, approve
from test_recordings import prepare_report, storage, video_file


def test_job_and_index_status_require_owner_role(api, account, storage):
    owner = account()
    author = account(role="author", organization_id=owner["organization_id"])
    _, recording_id, report = prepare_report(api, owner, storage)
    approve(api, owner, recording_id, report["revision"])
    job = api.post(f"/api/v1/recordings/{recording_id}/index", headers=owner["headers"])
    assert job.status_code == 202, job.text
    job_id = job.json()["id"]

    assert api.get(f"/api/v1/jobs/{job_id}", headers=author["headers"]).status_code == 403
    assert api.get(f"/api/v1/jobs/{job_id}", headers=owner["headers"]).status_code == 200
    assert api.get(f"/api/v1/recordings/{recording_id}/index", headers=author["headers"]).status_code == 403
    assert api.get(f"/api/v1/recordings/{recording_id}/index", headers=owner["headers"]).status_code == 200


def test_recording_search_includes_timestamp_ms(api, account, storage, monkeypatch):
    owner = account()
    recording_id = index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.recording_knowledge.OpenAIEmbeddingProvider", Embeddings)
    response = api.post("/api/v1/recordings/search", headers=owner["headers"], json={"query": "formulario"})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results and all("timestamp_ms" in item for item in results)
    # The one chunk carrying step evidence resolves to that step's first frame.
    assert any(item["timestamp_ms"] == 0 for item in results)


def test_unified_search_blends_video_and_procedure_hits(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    procedure_id, version_id = ready(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/approve", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/publish", headers=owner["headers"]).status_code == 200

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.search.OpenAIEmbeddingProvider", Embeddings)
    response = api.post("/api/v1/search", headers=owner["headers"], json={"query": "formulario cotizacion"})
    assert response.status_code == 200, response.text
    results = response.json()
    types = {item["type"] for item in results}
    assert "video" in types
    assert all(0.0 <= item["score"] <= 1.0 for item in results if item["type"] == "procedure")
    scores = [item["score"] for item in results]
    assert scores == sorted(scores, reverse=True)

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.post("/api/v1/search", headers=reader["headers"], json={"query": "formulario"}).status_code == 403


def test_master_usage_includes_published_procedure_topics(api, account):
    from test_master import make_platform_staff

    owner = account()
    procedure_id, version_id = ready(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/approve", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/publish", headers=owner["headers"]).status_code == 200

    staff = account()
    make_platform_staff(api, staff)
    usage = api.get("/api/v1/master/usage", headers=staff["headers"]).json()
    entry = next(e for e in usage if e["organization_id"] == owner["organization_id"])
    assert entry["topics"] == ["Cotizaciones"]


def test_chatbot_suggested_questions_from_history(api, account, storage, monkeypatch):
    owner = account()
    index_org(api, owner, storage)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.chatbot.OpenAIAnswerProvider", Answering)
    assert api.get("/api/v1/chatbot/suggested-questions", headers=owner["headers"]).json() == []
    asked = api.post("/api/v1/chatbot/ask", headers=owner["headers"],
                     json={"question": "Como se hace el formulario?"})
    assert asked.status_code == 200, asked.text
    suggestions = api.get("/api/v1/chatbot/suggested-questions", headers=owner["headers"]).json()
    assert suggestions == ["Como se hace el formulario?"]


def test_policy_suggested_questions_scoped_to_policy(api, account, policy_storage, monkeypatch):
    owner = account()
    policy_id = upload_and_index(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIAnswerProvider", Answering)
    assert api.get(f"/api/v1/policies/{policy_id}/suggested-questions", headers=owner["headers"]).json() == []
    asked = api.post("/api/v1/policies/ask", headers=owner["headers"], json={"question": "Cual es el deducible?"})
    assert asked.status_code == 200, asked.text
    suggestions = api.get(f"/api/v1/policies/{policy_id}/suggested-questions", headers=owner["headers"]).json()
    assert suggestions == ["Cual es el deducible?"]

    other = account()
    assert api.get(f"/api/v1/policies/{policy_id}/suggested-questions", headers=other["headers"]).status_code == 404


def test_reorder_steps_happy_path_and_rejects_non_permutation(api, account):
    owner = account()
    _, version_id = draft(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}/steps"
    ids = []
    for i in range(3):
        step = {"position": i + 1, "instruction": f"Paso {i + 1}", "expected_result": "Listo",
                "origin": "user_explained", "validation_status": "confirmed"}
        response = api.post(path, headers=owner["headers"], json=step)
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])

    reversed_order = list(reversed(ids))
    response = api.put(path + "/reorder", headers=owner["headers"], json={"step_ids": reversed_order})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["id"] for s in body] == reversed_order
    assert [s["position"] for s in body] == [1, 2, 3]

    listed = api.get(path, headers=owner["headers"]).json()
    assert [s["id"] for s in listed] == reversed_order

    bad = api.put(path + "/reorder", headers=owner["headers"], json={"step_ids": ids[:2]})
    assert bad.status_code == 409

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.put(path + "/reorder", headers=reader["headers"],
                   json={"step_ids": reversed_order}).status_code == 403
