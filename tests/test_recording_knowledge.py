from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from cognitive_os.infrastructure.ai.openai_curator import SupersedeDecision
from cognitive_os.infrastructure.ai.openai_embeddings import validate_vectors
from cognitive_os.infrastructure.database.models import Job, RecordingReport
from cognitive_os.workers.recording_index import run_index_once
from test_recordings import prepare_report, run_video, storage, video_file


class Embeddings:
    model_name = "text-embedding-3-small"

    def __init__(self, *args):
        pass

    def embed(self, texts):
        return [[1.0] + [0.0] * 1535 for _ in texts]

    def close(self):
        pass


def approve(api, owner, recording_id, revision):
    response = api.post(f"/api/v1/recordings/{recording_id}/report/review", headers=owner["headers"],
                        json={"revision": revision, "decision": "approved"})
    assert response.status_code == 200, response.text


def test_vector_index_real_pgvector_and_tenant_scope(api, account, storage, monkeypatch):
    owner, outsider = account(), account()
    _, recording_id, report = prepare_report(api, owner, storage)
    path = f"/api/v1/recordings/{recording_id}"
    assert api.post(path + "/index", headers=owner["headers"]).status_code == 409
    approve(api, owner, recording_id, report["revision"])
    job = api.post(path + "/index", headers=owner["headers"]).json()
    assert job["kind"] == "index_recording"
    assert run_index_once(api.app.state.engine, Embeddings(), UUID(owner["organization_id"]))
    assert not run_index_once(api.app.state.engine, Embeddings(), UUID(owner["organization_id"]))
    status = api.get(path + "/index", headers=owner["headers"]).json()
    assert status["indexed"] is True and status["chunks"] == 3
    assert api.post(path + "/index", headers=owner["headers"]).json()["id"] == job["id"]
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.recording_knowledge.OpenAIEmbeddingProvider", Embeddings)
    response = api.post("/api/v1/recordings/search", headers=owner["headers"], json={"query": "formulario"})
    assert response.status_code == 200, response.text
    assert len(response.json()["results"]) == 3
    assert response.json()["results"][0]["recording_id"] == recording_id
    assert api.post("/api/v1/recordings/search", headers=outsider["headers"], json={"query": "formulario"}).json()["results"] == []
    assert api.get(path + "/flow", headers=outsider["headers"]).status_code == 404
    # A stale derived index must not expose a revision that is no longer current.
    with Session(api.app.state.engine) as db, db.begin():
        db.get(RecordingReport, UUID(recording_id)).revision += 1
    assert api.post("/api/v1/recordings/search", headers=owner["headers"], json={"query": "formulario"}).json()["results"] == []


def test_index_failure_does_not_fail_analyzed_recording(api, account, storage):
    owner = account()
    _, recording_id, report = prepare_report(api, owner, storage)
    approve(api, owner, recording_id, report["revision"])
    with Session(api.app.state.engine) as db, db.begin():
        job = db.scalar(select(Job).where(Job.recording_id == UUID(recording_id), Job.kind == "index_recording"))
        job.max_attempts = 1
    class Broken(Embeddings):
        def embed(self, texts):
            raise RuntimeError("secret must never persist")
    assert run_index_once(api.app.state.engine, Broken(), UUID(owner["organization_id"]))
    path = f"/api/v1/recordings/{recording_id}"
    assert api.get(path, headers=owner["headers"]).json()["status"] == "ready"
    retry = api.post(path + "/index", headers=owner["headers"]).json()
    assert retry["status"] == "pending" and retry["attempts"] == 0


def test_flow_transcript_and_history(api, account, storage):
    owner = account()
    _, recording_id, report = prepare_report(api, owner, storage)
    path = f"/api/v1/recordings/{recording_id}"
    graph = api.get(path + "/flow", headers=owner["headers"]).json()
    assert graph["kind"] == "sequence" and graph["review_status"] == "pending"
    assert [node["id"] for node in graph["nodes"]] == ["start", "step-1", "end"]
    assert graph["nodes"][1]["data"]["frames"][0]["timestamp_ms"] == 0
    assert len(graph["edges"]) == 2
    assert api.get(path + "/transcript", headers=owner["headers"]).json()["analyzed"] is False
    approve(api, owner, recording_id, report["revision"])
    history = api.get(path + "/report/history", headers=owner["headers"]).json()
    assert history[0]["revision"] == 1 and history[0]["snapshot"]["review_status"] == "pending"


class AlwaysSupersede:
    """Fake curator: replaces every offered candidate with the new fragment.

    Mirrors OpenAIKnowledgeCurator's return shape without calling OpenAI, so the
    test exercises the supersede wiring in recording_index.py deterministically.
    """

    def curate(self, candidates):
        return [SupersedeDecision(new_chunk_index=item["new_chunk_index"],
                                  superseded_vector_ids=[existing["id"] for existing in item["existing"]])
                for item in candidates]


def test_knowledge_consolidation_supersedes_outdated_fragment(api, account, storage, monkeypatch):
    owner = account()
    session_id, recording_id, report = prepare_report(api, owner, storage)
    path = f"/api/v1/recordings/{recording_id}"
    approve(api, owner, recording_id, report["revision"])
    procedure_id = api.post(path + "/procedure", headers=owner["headers"]).json()["procedure_id"]
    org_id = UUID(owner["organization_id"])
    assert run_index_once(api.app.state.engine, Embeddings(), org_id)

    session2 = api.post("/api/v1/learning-sessions", headers=owner["headers"], json={
        "objective": "Actualizar formulario", "application_name": "Demo", "consent": True,
        "procedure_id": procedure_id}).json()
    data = {"idempotency_key": str(uuid4()), "media_type": "video/mp4", "size_bytes": 100, "consent": True}
    recording2 = api.post(f"/api/v1/learning-sessions/{session2['id']}/recordings",
                          headers=owner["headers"], json=data).json()["id"]
    path2 = f"/api/v1/recordings/{recording2}"
    assert api.post(path2 + "/complete", headers=owner["headers"]).status_code == 200
    assert api.post(path2 + "/process", headers=owner["headers"]).status_code == 202
    run_video(api, owner)
    report2 = api.get(path2 + "/report", headers=owner["headers"]).json()
    approve(api, owner, recording2, report2["revision"])
    assert api.post(path2 + "/index", headers=owner["headers"]).status_code == 202
    assert run_index_once(api.app.state.engine, Embeddings(), org_id, AlwaysSupersede(), 0.75)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.recording_knowledge.OpenAIEmbeddingProvider", Embeddings)

    with Session(api.app.state.engine) as db:
        rows = db.execute(text("SELECT recording_id, status, superseded_by FROM cognitive.recording_vectors "
                               "WHERE organization_id=:org"), {"org": org_id}).mappings().all()
    by_recording = {}
    for row in rows:
        by_recording.setdefault(str(row["recording_id"]), []).append(row)
    assert all(row["status"] == "superseded" and row["superseded_by"] is not None
              for row in by_recording[recording_id])
    assert all(row["status"] == "active" for row in by_recording[recording2])

    response = api.post("/api/v1/recordings/search", headers=owner["headers"], json={"query": "formulario"})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results and all(item["recording_id"] == recording2 for item in results)


def test_embedding_validation():
    for vectors in ([[0.0] * 1536], [[float("nan")] * 1536], [[1.0]], []):
        with pytest.raises(ValueError):
            validate_vectors(vectors, 1)
