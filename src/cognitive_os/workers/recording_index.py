import json

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from cognitive_os.application.recording_knowledge import report_chunks
from cognitive_os.infrastructure.ai.openai_embeddings import validate_vectors
from cognitive_os.infrastructure.database.models import RecordingReport
from cognitive_os.workers.consolidation import claim_job, fail_claim, owned_job


def run_index_once(engine, provider, organization_id=None):
    claim = claim_job(engine, 900, organization_id, kind="index_recording")
    if claim is None:
        return False
    try:
        with Session(engine) as db:
            report = db.scalar(select(RecordingReport).where(RecordingReport.recording_id == claim.recording_id,
                RecordingReport.organization_id == claim.organization_id))
            if report is None or report.review_status != "approved":
                raise ValueError("Only approved reports can be indexed")
            job = owned_job(db, claim)
            revision = report.revision
            expected = f"index_recording:{claim.recording_id}:{revision}:{provider.model_name}"
            if job.idempotency_key != expected:
                raise ValueError("Worker model differs from queued index model")
            chunks = report_chunks(report)
        vectors = validate_vectors(provider.embed([chunk["content"] for chunk in chunks]), len(chunks))
        with Session(engine) as db, db.begin():
            job = owned_job(db, claim)
            report = db.scalar(select(RecordingReport).where(RecordingReport.recording_id == claim.recording_id,
                RecordingReport.organization_id == claim.organization_id).with_for_update())
            if report.review_status != "approved" or report.revision != revision:
                raise ValueError("Report changed during indexing")
            params = {"org": claim.organization_id, "recording": claim.recording_id,
                      "revision": revision, "model": provider.model_name}
            db.execute(text("DELETE FROM cognitive.recording_vectors WHERE organization_id=:org "
                            "AND recording_id=:recording AND model_name=:model"), params)
            for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.execute(text("""INSERT INTO cognitive.recording_vectors
                    (organization_id,recording_id,report_revision,position,content,source,model_name,embedding)
                    VALUES (:org,:recording,:revision,:position,:content,CAST(:source AS jsonb),
                            :model,CAST(:embedding AS public.vector))"""),
                    {**params, "position": position, "content": chunk["content"],
                     "source": json.dumps(chunk["source"]), "embedding": json.dumps(vector)})
            job.status = "completed"
            job.completed_at = db.scalar(select(func.clock_timestamp()))
            job.locked_by = job.locked_until = job.last_error = None
    except Exception:
        fail_claim(engine, claim)
    return True
