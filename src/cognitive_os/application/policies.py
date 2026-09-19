"""Policy documents: ingested from Blob Storage (upload or folder sync), then
analyzed and indexed by workers/policy_index.py. Deliberately not modeled as
cognitive.jobs rows (every job there needs a session_id or version_id); the
status machine lives directly on policy_documents instead.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text

from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import PolicyDocument


def get_policy(db, member, policy_id, *, lock=False):
    query = select(PolicyDocument).where(PolicyDocument.id == policy_id,
                                          PolicyDocument.organization_id == member.organization_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise ApplicationError(404, "Policy document not found")
    return item


def list_policies(db, member):
    return db.scalars(select(PolicyDocument).where(
        PolicyDocument.organization_id == member.organization_id,
    ).order_by(PolicyDocument.created_at.desc())).all()


def create_policy(db, member, data, settings):
    existing = db.scalar(select(PolicyDocument).where(
        PolicyDocument.organization_id == member.organization_id,
        PolicyDocument.blob_key == f"{member.organization_id}/policies/upload-{data.idempotency_key}.pdf"))
    if existing:
        if (existing.size_bytes, existing.content_sha256, existing.title) != (
                data.size_bytes, data.content_sha256, data.title):
            raise ApplicationError(409, "This upload already exists with different data")
        return existing
    if data.size_bytes > settings.policy_max_bytes:
        raise ApplicationError(413, "Policy document exceeds size limit")
    item = PolicyDocument(organization_id=member.organization_id, source="upload",
                          size_bytes=data.size_bytes, content_sha256=data.content_sha256, title=data.title,
                          blob_key=f"{member.organization_id}/policies/upload-{data.idempotency_key}.pdf")
    db.add(item)
    db.commit()
    return item


def complete_policy(db, member, policy_id, store):
    item = get_policy(db, member, policy_id, lock=True)
    if item.status != "uploading":
        return item
    item.blob_snapshot = store.freeze(item)
    item.status = "queued"
    db.commit()
    return item


def retry_policy(db, member, policy_id):
    item = get_policy(db, member, policy_id, lock=True)
    if item.status != "failed":
        raise ApplicationError(409, "Only a failed policy document can be retried")
    item.status, item.attempts, item.error_code = "queued", 0, None
    item.locked_by = item.locked_until = None
    db.commit()
    return item


def retire_policy(db, member, policy_id):
    item = get_policy(db, member, policy_id, lock=True)
    if item.status not in ("ready", "failed"):
        raise ApplicationError(409, "Only a ready or failed policy document can be retired")
    item.status = "retired"
    db.commit()
    return item


def sync_policies(db, member, store, container, prefix):
    discovered = 0
    for blob in store.service.get_container_client(container).list_blobs(name_starts_with=prefix):
        if blob.size <= 0:
            continue
        existing = db.scalar(select(PolicyDocument).where(
            PolicyDocument.organization_id == member.organization_id, PolicyDocument.blob_key == blob.name))
        if existing:
            continue
        # A real snapshot, not just the current blob: later reprocessing reads
        # the exact bytes discovered now, even if the source file changes later.
        snapshot = store.service.get_blob_client(container, blob.name).create_snapshot()["snapshot"]
        title = blob.name.rsplit("/", 1)[-1]
        db.add(PolicyDocument(organization_id=member.organization_id, source="sync", status="queued",
                              size_bytes=blob.size, title=title, blob_key=blob.name, blob_snapshot=snapshot))
        discovered += 1
    db.commit()
    return discovered


def search_policy_vectors(db, organization_id, model, vector, limit, policy_id=None):
    query = """SELECT v.id, v.policy_id, p.title AS policy_title, v.content, v.source,
               1 - (v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector)) AS score
        FROM cognitive.policy_vectors v
        JOIN cognitive.policy_documents p ON p.id=v.policy_id AND p.organization_id=v.organization_id
        WHERE v.organization_id=:org AND v.model_name=:model AND p.status='ready'"""
    params = {"org": organization_id, "model": model, "vector": json.dumps(vector), "limit": limit}
    if policy_id is not None:
        query += " AND v.policy_id=:policy_id"
        params["policy_id"] = policy_id
    query += """ ORDER BY v.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector), v.id
        LIMIT :limit"""
    rows = db.execute(text(query), params)
    return [dict(row) for row in rows.mappings()]


def build_policy_citation(row):
    return {"policy_id": row["policy_id"], "policy_title": row["policy_title"],
            "label": row["source"].get("label", "Cláusula"), "score": round(row["score"], 4)}
