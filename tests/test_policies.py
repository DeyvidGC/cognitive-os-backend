from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cognitive_os.infrastructure.ai.openai_policy import PolicyAnalysis, PolicyClause
from cognitive_os.workers.policy_index import run_policy_index_once
from test_chatbot import Answering, Declining
from test_recording_knowledge import Embeddings

PDF_BYTES = b"%PDF-1.4 fake policy content"


class FakeBlob:
    def __init__(self, name, size):
        self.name = name
        self.size = size


class FakeContainerClient:
    def __init__(self, blobs):
        self.blobs = blobs

    def list_blobs(self, name_starts_with):
        return [b for b in self.blobs if b.name.startswith(name_starts_with)]


class FakeBlobClient:
    def __init__(self, counter):
        self.counter = counter

    def create_snapshot(self):
        self.counter[0] += 1
        return {"snapshot": f"snap-{self.counter[0]}"}


class FakeService:
    def __init__(self):
        self.blobs = []
        self._counter = [0]

    def get_container_client(self, container):
        return FakeContainerClient(self.blobs)

    def get_blob_client(self, container, name):
        return FakeBlobClient(self._counter)


@pytest.fixture
def policy_storage(monkeypatch):
    class Store:
        fail_freeze = False

        def __init__(self):
            self.service = FakeService()

        def transfer(self, item, write=False):
            return {"url": "https://example.invalid/test?fake-sas", "method": "PUT" if write else "GET",
                    "expires_at": datetime.now(UTC) + timedelta(minutes=5), "headers": {}}

        def freeze(self, item):
            from cognitive_os.domain.errors import ApplicationError
            if self.fail_freeze:
                raise ApplicationError(409, "Uploaded policy size does not match reservation")
            return "snapshot-1"

        def download(self, item, target):
            target.write_bytes(PDF_BYTES)

    store = Store()

    @contextmanager
    def factory(settings):
        yield store

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.recording_store", factory)
    monkeypatch.setattr("cognitive_os.workers.policy_index.recording_store", factory)
    return store


class Analyzing:
    def __init__(self, *args):
        pass

    def analyze(self, pdf_bytes):
        assert pdf_bytes == PDF_BYTES
        return PolicyAnalysis(title="Poliza Auto", clauses=[PolicyClause(label="8.2", text="Deducible del 10%.")])

    def close(self):
        pass


def upload_and_index(api, owner, title=""):
    response = api.post("/api/v1/policies", headers=owner["headers"],
                        json={"idempotency_key": str(uuid4()), "size_bytes": len(PDF_BYTES), "title": title})
    assert response.status_code == 201, response.text
    policy_id = response.json()["id"]
    assert api.post(f"/api/v1/policies/{policy_id}/upload-url", headers=owner["headers"]).status_code == 200
    complete = api.post(f"/api/v1/policies/{policy_id}/complete", headers=owner["headers"])
    assert complete.status_code == 200 and complete.json()["status"] == "queued", complete.text
    assert run_policy_index_once(api.app.state.engine, Embeddings(), Analyzing(), api.app.state.settings,
                                 UUID(owner["organization_id"]))
    status = api.get(f"/api/v1/policies/{policy_id}", headers=owner["headers"]).json()
    assert status["status"] == "ready", status
    return policy_id


def test_upload_and_index_policy(api, account, policy_storage):
    owner = account()
    policy_id = upload_and_index(api, owner)
    status = api.get(f"/api/v1/policies/{policy_id}", headers=owner["headers"]).json()
    assert status["title"] == "Poliza Auto"

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.post("/api/v1/policies", headers=reader["headers"], json={
        "idempotency_key": str(uuid4()), "size_bytes": 10}).status_code == 403
    assert api.get("/api/v1/policies", headers=reader["headers"]).status_code == 200

    outsider = account()
    assert api.get(f"/api/v1/policies/{policy_id}", headers=outsider["headers"]).status_code == 404


def test_sync_discovers_untracked_blobs_and_skips_duplicates(api, account, policy_storage):
    owner = account()
    prefix = f"{owner['organization_id']}/policies/"
    policy_storage.service.blobs = [FakeBlob(prefix + "manual-upload.pdf", len(PDF_BYTES))]

    response = api.post("/api/v1/policies/sync", headers=owner["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["discovered"] == 1

    again = api.post("/api/v1/policies/sync", headers=owner["headers"])
    assert again.json()["discovered"] == 0

    listing = api.get("/api/v1/policies", headers=owner["headers"]).json()
    assert len(listing) == 1 and listing[0]["status"] == "queued"

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.post("/api/v1/policies/sync", headers=reader["headers"]).status_code == 403


def test_ask_answers_with_clause_citation(api, account, policy_storage, monkeypatch):
    owner = account()
    policy_id = upload_and_index(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIAnswerProvider", Answering)

    response = api.post("/api/v1/policies/ask", headers=owner["headers"],
                        json={"question": "Cual es el deducible por robo total?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gap_detected"] is False
    assert body["citation"]["policy_id"] == policy_id
    assert body["citation"]["label"] == "8.2"

    usage = api.get("/api/v1/usage/summary", headers=owner["headers"]).json()
    assert usage["answered"] == 1 and usage["top_questions"][0]["topic"] == "Poliza Auto"


def test_ask_records_gap_when_not_confident(api, account, policy_storage, monkeypatch):
    owner = account()
    upload_and_index(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIAnswerProvider", Declining)

    response = api.post("/api/v1/policies/ask", headers=owner["headers"], json={"question": "Pregunta sin respaldo"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gap_detected"] is True and body["gap"]["asked_count"] == 1

    gaps = api.get("/api/v1/chatbot/gaps", headers=owner["headers"]).json()
    assert len(gaps) == 1


def test_view_returns_signed_url_and_retire_removes_from_answers(api, account, policy_storage, monkeypatch):
    owner = account()
    policy_id = upload_and_index(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIEmbeddingProvider", Embeddings)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.policies.OpenAIAnswerProvider", Answering)

    view = api.get(f"/api/v1/policies/{policy_id}/view", headers=owner["headers"])
    assert view.status_code == 200 and view.json()["method"] == "GET"

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.post(f"/api/v1/policies/{policy_id}/retire", headers=reader["headers"]).status_code == 403
    retired = api.post(f"/api/v1/policies/{policy_id}/retire", headers=owner["headers"])
    assert retired.status_code == 200 and retired.json()["status"] == "retired"
    assert api.post(f"/api/v1/policies/{policy_id}/retire", headers=owner["headers"]).status_code == 409

    response = api.post("/api/v1/policies/ask", headers=owner["headers"],
                        json={"question": "Cual es el deducible por robo total?"})
    assert response.json()["gap_detected"] is True, "a retired policy must not answer questions anymore"


class FailingAnalyzing:
    def __init__(self, *args):
        pass

    def analyze(self, pdf_bytes):
        raise ValueError("boom")

    def close(self):
        pass


def test_retry_recovers_a_failed_policy(api, account, policy_storage):
    owner = account()
    response = api.post("/api/v1/policies", headers=owner["headers"],
                        json={"idempotency_key": str(uuid4()), "size_bytes": len(PDF_BYTES)})
    policy_id = response.json()["id"]
    api.post(f"/api/v1/policies/{policy_id}/upload-url", headers=owner["headers"])
    api.post(f"/api/v1/policies/{policy_id}/complete", headers=owner["headers"])

    for _ in range(3):
        assert run_policy_index_once(api.app.state.engine, Embeddings(), FailingAnalyzing(),
                                     api.app.state.settings, UUID(owner["organization_id"]))
    assert api.get(f"/api/v1/policies/{policy_id}", headers=owner["headers"]).json()["status"] == "failed"

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.post(f"/api/v1/policies/{policy_id}/retry", headers=reader["headers"]).status_code == 403

    retried = api.post(f"/api/v1/policies/{policy_id}/retry", headers=owner["headers"])
    assert retried.status_code == 200 and retried.json()["status"] == "queued"

    assert run_policy_index_once(api.app.state.engine, Embeddings(), Analyzing(), api.app.state.settings,
                                 UUID(owner["organization_id"]))
    assert api.get(f"/api/v1/policies/{policy_id}", headers=owner["headers"]).json()["status"] == "ready"
