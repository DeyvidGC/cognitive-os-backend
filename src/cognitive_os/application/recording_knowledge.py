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
        job.stage, job.progress_percent = "queued", 0
        job.available_at = datetime.now(UTC)
        job.completed_at = job.locked_by = job.locked_until = job.last_error = None
    return job


def report_chunks(report):
    content = report.content
    parts = [(content["title"] + "\n" + content["summary"], {"kind": "summary", "frame_indices": []})]
    parts.append((content["report"], {"kind": "report", "frame_indices": []}))
    for kind in ("prerequisites", "business_rules", "exceptions"):
        for fact in content.get(kind, []):
            parts.append((fact["text"], {"kind": kind, "frame_indices": fact["frame_indices"],
                                        "text_sources": fact.get("text_sources", [])}))
    for index, step in enumerate(content["instructions"], 1):
        routes = "\n".join(f"{item['condition']}: {item['target_step'] or 'fin'}"
                           for item in step.get("alternatives", []))
        parts.append((step["instruction"] + "\n" + step["expected_result"] + "\n" + routes,
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
        WHERE v.organization_id=:org AND v.model_name=:model AND v.status='active'
          AND p.review_status='approved' AND r.status='ready'
        ORDER BY v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector), v.id
        LIMIT :limit
    """), {"org": organization_id, "model": model, "vector": json.dumps(vector), "limit": limit})
    return [dict(row) for row in rows.mappings()]


def find_supersede_candidates(db, organization_id, procedure_id, recording_id, model, vector, threshold, limit=3):
    """Active fragments from OTHER recordings of the same procedure that a new,
    near-duplicate fragment might update. A cheap embedding pre-filter so the
    curator model only ever judges a handful of already-similar pairs."""
    if procedure_id is None:
        return []
    rows = db.execute(text("""
        SELECT v.id, v.content,
               1 - (v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector)) AS score
        FROM cognitive.recording_vectors v
        JOIN cognitive.recordings r ON r.id=v.recording_id AND r.organization_id=v.organization_id
        JOIN cognitive.learning_sessions s ON s.id=r.session_id AND s.organization_id=r.organization_id
        WHERE v.organization_id=:org AND v.model_name=:model AND v.status='active'
          AND s.procedure_id=:procedure_id AND v.recording_id != :recording_id
        ORDER BY v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector), v.id
        LIMIT :limit
    """), {"org": organization_id, "model": model, "vector": json.dumps(vector),
           "procedure_id": procedure_id, "recording_id": recording_id, "limit": limit})
    return [dict(row) for row in rows.mappings() if row["score"] >= threshold]


def report_flow(report):
    from cognitive_os.schemas.recordings import VisualReportContent
    content = VisualReportContent.model_validate(report.content)
    base = {"schema_version": 2, "recording_id": report.recording_id, "revision": report.revision,
            "review_status": report.review_status, "title": content.title,
            "uncertainties": content.uncertainties,
            "prerequisites": [item.model_dump() for item in content.prerequisites],
            "business_rules": [item.model_dump() for item in content.business_rules],
            "exceptions": [item.model_dump() for item in content.exceptions],
            "layout": {"direction": "TB", "node_width": 320, "gap": 70}}
    if not content.instructions:
        return {**base, "kind": "sequence", "nodes": [], "edges": [], "empty_reason": "insufficient_evidence"}
    nodes = [{"id": "start", "type": "input", "position": {"x": 0, "y": 0},
              "data": {"label": "Inicio"}}]
    edges = [{"id": "edge-start", "source": "start", "target": "step-1"}]
    frames = report.sampling.get("frames", [])
    y = 140
    for index, instruction in enumerate(content.instructions, 1):
        step = instruction.model_dump()
        evidence = [frames[i] for i in step["frame_indices"] if 0 <= i < len(frames)]
        times = [frame["timestamp_ms"] for frame in evidence]
        height = 70 + ((len(step["instruction"]) + 37) // 38) * 22
        nodes.append({"id": f"step-{index}", "type": "default", "position": {"x": 0, "y": y},
                      "data": {"label": step["instruction"], "expected_result": step["expected_result"],
                               "step_number": index, "node_kind": "decision" if instruction.alternatives else "action",
                               "frame_indices": step["frame_indices"], "frames": evidence,
                               "text_sources": step["text_sources"], "suggested_height": height,
                               "evidence_start_ms": min(times) if times else None,
                               "evidence_end_ms": max(times) if times else None,
                               "origin": "visual_and_text" if evidence and step["text_sources"] else
                                         "visual" if evidence else "text",
                               "validation_status": report.review_status}})
        y += height + 70
        if instruction.alternatives:
            for branch, alternative in enumerate(instruction.alternatives):
                edges.append({"id": f"edge-{index}-{branch}", "source": f"step-{index}",
                              "target": f"step-{alternative.target_step}" if alternative.target_step else "end",
                              "label": alternative.condition, "data": {"kind": "conditional"}})
        else:
            edges.append({"id": f"edge-{index}", "source": f"step-{index}",
                          "target": f"step-{index + 1}" if index < len(content.instructions) else "end"})
    nodes.append({"id": "end", "type": "output", "position": {"x": 0, "y": y},
                  "data": {"label": "Fin"}})
    return {**base, "kind": "conditional" if any(step.alternatives for step in content.instructions) else "sequence",
            "nodes": nodes, "edges": edges}
