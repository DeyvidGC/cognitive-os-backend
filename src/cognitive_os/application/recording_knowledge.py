from datetime import UTC, datetime
import json

from sqlalchemy import select, text

from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import Job


def enqueue_index(db, recording, report, model, *, retry=False):
    if report.review_status != "approved":
        raise ApplicationError(409, "Approve the report before indexing")
    key = f"index_recording:{recording.id}:{report.revision}:{model}"
    job = db.scalar(select(Job).where(Job.organization_id == recording.organization_id,
                                      Job.idempotency_key == key).with_for_update())
    if job is None:
        job = Job(organization_id=recording.organization_id, recording_id=recording.id,
                  session_id=recording.session_id, kind="index_recording", idempotency_key=key)
        db.add(job)
    elif retry and job.status == "failed":
        job.status, job.attempts = "pending", 0
        job.available_at = datetime.now(UTC)
        job.completed_at = job.locked_by = job.locked_until = job.last_error = None
    return job


def report_chunks(report):
    content = report.content
    parts = [(content["title"] + "\n" + content["summary"], {"kind": "summary", "frame_indices": []})]
    parts.append((content["report"], {"kind": "report", "frame_indices": []}))
    for index, step in enumerate(content["instructions"], 1):
        parts.append((step["instruction"] + "\n" + step["expected_result"],
                      {"kind": "step", "step": index, "frame_indices": step["frame_indices"],
                       "text_sources": step.get("text_sources", [])}))
    # Character chunks stay below the embedding byte/token limit even with multibyte text.
    result = []
    for value, source in parts:
        for offset in range(0, len(value), 1200):
            chunk = value[offset:offset + 1200].strip()
            if chunk:
                result.append({"content": chunk, "source": source})
    if not result or len(result) > 400:
        raise ValueError("Report exceeds indexing budget")
    return result


def search_vectors(db, organization_id, model, vector, limit):
    # Exact tenant-scoped cosine ranking avoids approximate-index tenant recall loss.
    rows = db.execute(text("""
        SELECT v.id, v.recording_id, r.session_id, v.report_revision, v.content, v.source,
               1 - (v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector)) AS score
        FROM cognitive.recording_vectors v
        JOIN cognitive.recording_reports p ON p.recording_id=v.recording_id
          AND p.organization_id=v.organization_id AND p.revision=v.report_revision
        JOIN cognitive.recordings r ON r.id=v.recording_id AND r.organization_id=v.organization_id
        WHERE v.organization_id=:org AND v.model_name=:model
          AND p.review_status='approved' AND r.status='ready'
        ORDER BY v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector), v.id
        LIMIT :limit
    """), {"org": organization_id, "model": model, "vector": json.dumps(vector), "limit": limit})
    return [dict(row) for row in rows.mappings()]


def report_flow(report):
    nodes = [{"id": "start", "type": "input", "position": {"x": 0, "y": 0},
              "data": {"label": "Inicio"}}]
    frames = report.sampling.get("frames", [])
    for index, step in enumerate(report.content["instructions"], 1):
        nodes.append({"id": f"step-{index}", "type": "default", "position": {"x": 0, "y": index * 160},
                      "data": {"label": step["instruction"], "expected_result": step["expected_result"],
                               "frame_indices": step["frame_indices"],
                               "frames": [frames[i] for i in step["frame_indices"] if 0 <= i < len(frames)],
                               "text_sources": step.get("text_sources", []),
                               "validation_status": report.review_status}})
    nodes.append({"id": "end", "type": "output", "position": {"x": 0, "y": len(nodes) * 160},
                  "data": {"label": "Fin"}})
    edges = [{"id": f"edge-{i}", "source": nodes[i]["id"], "target": nodes[i + 1]["id"]}
             for i in range(len(nodes) - 1)]
    return {"schema_version": 1, "recording_id": report.recording_id, "revision": report.revision,
            "review_status": report.review_status, "title": report.content["title"],
            "kind": "sequence", "nodes": nodes, "edges": edges,
            "uncertainties": report.content["uncertainties"]}
