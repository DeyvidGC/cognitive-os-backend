import json
import logging
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from cognitive_os.infrastructure.ai.openai_policy import policy_chunks
from cognitive_os.infrastructure.database.models import PolicyDocument
from cognitive_os.infrastructure.storage.azure_recordings import recording_store


def claim_policy(engine, lease_seconds=600, organization_id=None):
    with Session(engine, expire_on_commit=False) as db, db.begin():
        now = db.scalar(select(func.clock_timestamp()))
        query = select(PolicyDocument).where(
            (PolicyDocument.status == "queued")
            | ((PolicyDocument.status == "processing") & (PolicyDocument.locked_until <= now)))
        if organization_id is not None:
            query = query.where(PolicyDocument.organization_id == organization_id)
        item = db.scalar(query.order_by(PolicyDocument.created_at).with_for_update(skip_locked=True).limit(1))
        if item is None:
            return None
        if item.attempts >= 3:
            item.status, item.error_code = "failed", "policy_attempts_exhausted"
            item.locked_by = item.locked_until = None
            return None
        token = uuid4().hex
        item.status = "processing"
        item.attempts += 1
        item.locked_by = token
        item.locked_until = now + timedelta(seconds=lease_seconds)
        return item.id, item.organization_id, token


def _owned(db, policy_id, organization_id, token):
    item = db.scalar(select(PolicyDocument).where(
        PolicyDocument.id == policy_id, PolicyDocument.organization_id == organization_id).with_for_update())
    now = db.scalar(select(func.clock_timestamp()))
    if item is None or item.status != "processing" or item.locked_by != token or item.locked_until <= now:
        raise ValueError("Policy lease lost")
    return item


def fail_claim(engine, policy_id, organization_id, token, exc=None):
    with Session(engine) as db, db.begin():
        try:
            item = _owned(db, policy_id, organization_id, token)
        except ValueError:
            return
        item.locked_by = item.locked_until = None
        if item.attempts >= 3:
            item.status, item.error_code = "failed", "policy_processing_failed"
        else:
            item.status = "queued"
    # Never persist exception strings: SDK/driver errors may include sensitive input.
    logging.getLogger(__name__).warning("Policy %s processing failed: %r", policy_id, type(exc).__name__)


def run_policy_index_once(engine, embedding_provider, policy_provider, settings, organization_id=None):
    claim = claim_policy(engine, settings.policy_lease_seconds, organization_id)
    if claim is None:
        return False
    policy_id, org_id, token = claim
    try:
        with Session(engine) as db:
            item = db.get(PolicyDocument, policy_id)
            blob_key, blob_snapshot, size_bytes, content_sha256 = (
                item.blob_key, item.blob_snapshot, item.size_bytes, item.content_sha256)
            existing_title = item.title
        with TemporaryDirectory(prefix="cognitive-policy-") as temp, recording_store(settings) as store:
            path = Path(temp) / "policy.pdf"
            store.download(_DownloadTarget(blob_key, blob_snapshot, size_bytes, content_sha256), path)
            pdf_bytes = path.read_bytes()
        analysis = policy_provider.analyze(pdf_bytes)
        chunks = policy_chunks(analysis)
        vectors = embedding_provider.embed([chunk["content"] for chunk in chunks])
        with Session(engine, expire_on_commit=False) as db, db.begin():
            item = _owned(db, policy_id, org_id, token)
            db.execute(text("DELETE FROM cognitive.policy_vectors WHERE organization_id=:org AND policy_id=:policy"),
                      {"org": org_id, "policy": policy_id})
            for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.execute(text("""INSERT INTO cognitive.policy_vectors
                    (id, organization_id, policy_id, position, content, source, model_name, embedding)
                    VALUES (:id, :org, :policy, :position, :content, CAST(:source AS jsonb),
                            :model, CAST(:embedding AS public.vector))"""),
                    {"id": uuid4(), "org": org_id, "policy": policy_id, "position": position,
                     "content": chunk["content"], "source": json.dumps(chunk["source"]),
                     "model": embedding_provider.model_name, "embedding": json.dumps(vector)})
            item.title = existing_title or analysis.title
            item.model_name = embedding_provider.model_name
            item.status = "ready"
            item.analyzed_at = datetime.now(UTC)
            item.locked_by = item.locked_until = item.error_code = None
    except Exception as exc:
        fail_claim(engine, policy_id, org_id, token, exc)
    return True


class _DownloadTarget:
    """Minimal duck-typed view of PolicyDocument for AzureRecordingStore.download,
    built from plain values so the download step never holds a DB session open."""

    def __init__(self, blob_key, blob_snapshot, size_bytes, content_sha256):
        self.blob_key = blob_key
        self.blob_snapshot = blob_snapshot
        self.size_bytes = size_bytes
        self.content_sha256 = content_sha256
