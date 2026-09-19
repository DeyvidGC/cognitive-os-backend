import json
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from cognitive_os.application.recording_knowledge import find_supersede_candidates, report_chunks
from cognitive_os.infrastructure.ai.openai_embeddings import validate_vectors
from cognitive_os.infrastructure.database.models import LearningSession, Recording, RecordingReport
from cognitive_os.workers.consolidation import claim_job, fail_claim, owned_job, set_stage


def consolidate_knowledge(db, organization_id, procedure_id, recording_id, model, curator, threshold, rows):
    """Mark active fragments from OTHER recordings of the same procedure as superseded
    when the curator model confirms a new fragment updates the same specific fact.

    rows: [(new_id, content, embedding_vector)] for the fragments about to be inserted.
    Runs only when the recording is tied to a procedure and candidates exist, so a
    first-time or standalone recording never calls the curator model at all.
    """
    if procedure_id is None or curator is None:
        return
    candidates_by_index = {}
    for index, (_, content, vector) in enumerate(rows):
        found = find_supersede_candidates(db, organization_id, procedure_id, recording_id, model, vector, threshold)
        if found:
            candidates_by_index[index] = found
    if not candidates_by_index:
        return
    payload = [{"new_chunk_index": index, "new_text": rows[index][1],
                "existing": [{"id": str(item["id"]), "text": item["content"]} for item in found]}
               for index, found in candidates_by_index.items()]
    for decision in curator.curate(payload):
        found = candidates_by_index.get(decision.new_chunk_index)
        if found is None:
            continue
        offered_ids = {str(item["id"]) for item in found}
        new_id = rows[decision.new_chunk_index][0]
        for old_id in decision.superseded_vector_ids:
            if old_id not in offered_ids:
                continue
            db.execute(text("""UPDATE cognitive.recording_vectors SET status='superseded', superseded_by=:new_id
                WHERE id=:old_id AND organization_id=:org AND status='active'"""),
                {"new_id": new_id, "old_id": old_id, "org": organization_id})


def run_index_once(engine, provider, organization_id=None, curator=None, supersede_threshold=0.75):
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
            recording = db.get(Recording, claim.recording_id)
            procedure_id = db.scalar(select(LearningSession.procedure_id).where(
                LearningSession.id == recording.session_id, LearningSession.organization_id == claim.organization_id))
        set_stage(engine, claim, "embedding", 30)
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
            rows = [(uuid4(), chunk["content"], vector) for chunk, vector in zip(chunks, vectors, strict=True)]
            # Insert the new fragments before marking anything superseded: superseded_by
            # references the new row, so it must already exist to satisfy the foreign key.
            for position, (chunk, (new_id, content, vector)) in enumerate(zip(chunks, rows)):
                db.execute(text("""INSERT INTO cognitive.recording_vectors
                    (id,organization_id,recording_id,report_revision,position,content,source,model_name,embedding)
                    VALUES (:id,:org,:recording,:revision,:position,:content,CAST(:source AS jsonb),
                            :model,CAST(:embedding AS public.vector))"""),
                    {**params, "id": new_id, "position": position, "content": content,
                     "source": json.dumps(chunk["source"]), "embedding": json.dumps(vector)})
            consolidate_knowledge(db, claim.organization_id, procedure_id, claim.recording_id,
                                  provider.model_name, curator, supersede_threshold, rows)
            job.status = "completed"
            job.stage, job.progress_percent = "completed", 100
            job.completed_at = db.scalar(select(func.clock_timestamp()))
            job.locked_by = job.locked_until = job.last_error = None
    except Exception as exc:
        fail_claim(engine, claim, exc)
    return True
