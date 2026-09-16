from uuid import UUID, uuid4

import pytest

from cognitive_os.application.orchestration import GeneratedDraft, build_draft_graph


class FakeProvider:
    model_name = "test-provider"

    def generate(self, source):
        return GeneratedDraft(title="Registro", summary="Registrar datos",
                              steps=[{"instruction": "Guardar", "expected_result": "Guardado",
                                      "source_event_ids": [source["events"][0]["id"]]}])


def test_graph_rejects_invented_source_references():
    class InvalidProvider(FakeProvider):
        def generate(self, source):
            draft = super().generate(source)
            draft.steps[0].source_event_ids = [uuid4()]
            return draft

    with pytest.raises(ValueError, match="Unknown source"):
        build_draft_graph(InvalidProvider()).invoke({"source": {"events": [{"id": str(uuid4())}]}})


def test_graph_produces_validated_draft():
    event_id = uuid4()
    result = build_draft_graph(FakeProvider()).invoke({"source": {"events": [{"id": str(event_id)}]}})
    assert result["draft"].steps[0].source_event_ids == [event_id]


def enqueue(api, account):
    owner = account()
    response = api.post("/api/v1/learning-sessions", headers=owner["headers"], json={
        "objective": "Registrar datos", "application_name": "Demo", "consent": True})
    assert response.status_code == 201
    session_id = response.json()["id"]
    response = api.post(f"/api/v1/learning-sessions/{session_id}/events", headers=owner["headers"], json={
        "idempotency_key": "one", "sequence_number": 1, "offset_ms": 0,
        "event_type": "message", "text": "Guardar los datos del formulario"})
    assert response.status_code == 200
    response = api.post(f"/api/v1/learning-sessions/{session_id}/finish", headers=owner["headers"])
    assert response.status_code == 202
    return owner, session_id, response.json()["id"]


def test_worker_draft_is_atomic_private_and_not_published(api, account):
    from cognitive_os.workers.consolidation import run_once

    owner, session_id, job_id = enqueue(api, account)
    assert run_once(api.app.state.engine, FakeProvider(), organization_id=UUID(owner["organization_id"]))
    job = api.get(f"/api/v1/jobs/{job_id}", headers=owner["headers"]).json()
    assert job["status"] == "completed"
    assert job["version_id"]
    path = f"/api/v1/procedure-versions/{job['version_id']}"
    assert api.get(path, headers=owner["headers"]).json()["status"] == "draft"
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 409
    outsider = account()
    assert api.get(path, headers=outsider["headers"]).status_code == 404
    assert api.get(f"/api/v1/learning-sessions/{session_id}", headers=owner["headers"]).json()["status"] == "completed"
    assert api.post(f"/api/v1/learning-sessions/{session_id}/finish", headers=owner["headers"]).json()["id"] == job_id


def test_expired_claim_cannot_overwrite_new_worker(api, account):
    from datetime import UTC, datetime, timedelta
    from sqlalchemy.orm import Session
    from cognitive_os.infrastructure.database.models import Job
    from cognitive_os.workers.consolidation import claim_job, load_source, save_draft

    owner, _, _ = enqueue(api, account)
    engine = api.app.state.engine
    first = claim_job(engine, organization_id=UUID(owner["organization_id"]))
    with Session(engine) as db, db.begin():
        db.get(Job, first.job_id).locked_until = datetime.now(UTC) - timedelta(seconds=1)
    second = claim_job(engine, organization_id=UUID(owner["organization_id"]))
    assert first.job_id == second.job_id and first.token != second.token
    draft = FakeProvider().generate(load_source(engine, second))
    with pytest.raises(ValueError, match="lease lost"):
        save_draft(engine, first, draft, "fake")
    save_draft(engine, second, draft, "fake")


def test_provider_failure_is_redacted_and_retries_are_bounded(api, account):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID
    from sqlalchemy.orm import Session
    from cognitive_os.infrastructure.database.models import Job
    from cognitive_os.workers.consolidation import run_once

    class FailingProvider(FakeProvider):
        def generate(self, source):
            raise RuntimeError("DO-NOT-LOG-secret-captured-text")

    owner, session_id, job_id = enqueue(api, account)
    engine = api.app.state.engine
    for attempt in range(3):
        assert run_once(engine, FailingProvider(), organization_id=UUID(owner["organization_id"]))
        with Session(engine) as db, db.begin():
            job = db.get(Job, UUID(job_id))
            assert job.last_error == "consolidation_failed"
            assert job.attempts == attempt + 1
            assert job.status == ("failed" if attempt == 2 else "pending")
            job.available_at = datetime.now(UTC) - timedelta(seconds=1)
    assert api.get(f"/api/v1/learning-sessions/{session_id}", headers=owner["headers"]).json()["status"] == "failed"


def test_concurrent_workers_claim_a_job_only_once(api, account):
    from concurrent.futures import ThreadPoolExecutor
    from cognitive_os.workers.consolidation import claim_job

    owner, _, _ = enqueue(api, account)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim_job(api.app.state.engine,
                           organization_id=UUID(owner["organization_id"])), range(2)))
    assert sum(c is not None for c in claims) == 1


def test_openai_adapter_uses_requested_model_without_network(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from cognitive_os.core.config import Settings
    from cognitive_os.infrastructure.ai.openai_drafts import OpenAIDraftProvider

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    client = MagicMock()
    monkeypatch.setattr("cognitive_os.infrastructure.ai.openai_drafts.OpenAI", lambda **kwargs: client)
    source = {"events": [{"id": str(uuid4())}]}
    draft = FakeProvider().generate(source)
    client.responses.parse.return_value = SimpleNamespace(status="completed", output_parsed=draft)
    provider = OpenAIDraftProvider(Settings(_env_file=None))
    assert provider.generate(source) == draft
    assert client.responses.parse.call_args.kwargs["model"] == "gpt-5.6-luna"
    assert client.responses.parse.call_args.kwargs["store"] is False
    client.responses.parse.return_value = SimpleNamespace(status="incomplete", output_parsed=None)
    with pytest.raises(ValueError):
        provider.generate(source)
    provider.close()
