"""Knowledge chatbot: answers only from published, approved knowledge and
tracks every question it cannot answer as a knowledge gap, deduplicated by
embedding similarity so the same unanswered question doesn't pile up rows.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text

from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.models import AuditEvent, LearningSession

_GAP_COLUMNS = "id, question, asked_count, status, best_score, created_at, last_asked_at"


def citation_label(source):
    kind = source.get("kind")
    if kind == "step":
        return f"paso {source.get('step')}"
    return {"business_rules": "Regla de negocio", "prerequisites": "Requisito previo",
            "exceptions": "Excepción", "summary": "Resumen del procedimiento",
            "report": "Descripción del proceso"}.get(kind, "Conocimiento publicado")


def build_citation(db, organization_id, row):
    session = db.scalar(select(LearningSession).where(
        LearningSession.id == row["session_id"], LearningSession.organization_id == organization_id))
    return {"recording_id": row["recording_id"], "session_objective": session.objective if session else None,
            "label": citation_label(row["source"]), "score": round(row["score"], 4)}


def _gap_dict(row):
    return {"id": row["id"], "question": row["question"], "asked_count": row["asked_count"],
            "status": row["status"], "best_score": row["best_score"],
            "created_at": row["created_at"], "last_asked_at": row["last_asked_at"]}


def _load_gap(db, organization_id, gap_id):
    row = db.execute(text(f"SELECT {_GAP_COLUMNS} FROM cognitive.knowledge_gaps "
                          "WHERE id=:id AND organization_id=:org"),
                     {"id": gap_id, "org": organization_id}).mappings().first()
    return _gap_dict(row)


def record_gap(db, member, model_name, question, vector, best_score, dedup_threshold):
    match = db.execute(text("""
        SELECT id FROM cognitive.knowledge_gaps
        WHERE organization_id=:org AND model_name=:model AND status='open'
          AND 1 - (embedding OPERATOR(public.<=>) CAST(:vector AS public.vector)) >= :threshold
        ORDER BY embedding OPERATOR(public.<=>) CAST(:vector AS public.vector)
        LIMIT 1
    """), {"org": member.organization_id, "model": model_name, "vector": json.dumps(vector),
           "threshold": dedup_threshold}).mappings().first()
    now = datetime.now(UTC)
    if match:
        gap_id = match["id"]
        db.execute(text("""UPDATE cognitive.knowledge_gaps SET asked_count = asked_count + 1,
            last_asked_at=:now, best_score = GREATEST(COALESCE(best_score, 0), COALESCE(:score, 0))
            WHERE id=:id AND organization_id=:org"""),
            {"now": now, "score": best_score, "id": gap_id, "org": member.organization_id})
    else:
        gap_id = uuid4()
        db.execute(text("""INSERT INTO cognitive.knowledge_gaps
            (id, organization_id, question, model_name, embedding, asked_count, status, best_score, last_asked_at)
            VALUES (:id, :org, :question, :model, CAST(:vector AS public.vector), 1, 'open', :score, :now)"""),
            {"id": gap_id, "org": member.organization_id, "question": question, "model": model_name,
             "vector": json.dumps(vector), "score": best_score, "now": now})
    db.add(AuditEvent(organization_id=member.organization_id, actor_id=member.user_id,
                      action="chatbot.gap_detected", resource_type="knowledge_gap", resource_id=gap_id,
                      details={"question": question}))
    return _load_gap(db, member.organization_id, gap_id)


def list_gaps(db, member, status="open"):
    rows = db.execute(text(f"""SELECT {_GAP_COLUMNS} FROM cognitive.knowledge_gaps
        WHERE organization_id=:org AND status=:status
        ORDER BY asked_count DESC, last_asked_at DESC LIMIT 100"""),
        {"org": member.organization_id, "status": status}).mappings().all()
    return [_gap_dict(row) for row in rows]


def log_query(db, member, model_name, question, *, answered, session_objective=None,
              recording_id=None, policy_id=None, gap_id=None):
    db.execute(text("""INSERT INTO cognitive.chat_queries
        (organization_id, user_id, question, answered, session_objective, recording_id, policy_id, gap_id, model_name)
        VALUES (:org, :user, :question, :answered, :objective, :recording, :policy, :gap, :model)"""),
        {"org": member.organization_id, "user": member.user_id, "question": question,
         "answered": answered, "objective": session_objective, "recording": recording_id,
         "policy": policy_id, "gap": gap_id, "model": model_name})


def history(db, member, limit=20):
    rows = db.execute(text("""SELECT id, question, answered, session_objective, recording_id,
        policy_id, created_at FROM cognitive.chat_queries WHERE organization_id=:org
        ORDER BY created_at DESC LIMIT :limit"""),
        {"org": member.organization_id, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def resolve_gap(db, member, gap_id):
    result = db.execute(text("""UPDATE cognitive.knowledge_gaps SET status='resolved',
        resolved_at=:now, resolved_by=:user
        WHERE id=:id AND organization_id=:org AND status='open'"""),
        {"now": datetime.now(UTC), "user": member.user_id, "id": gap_id, "org": member.organization_id})
    if result.rowcount == 0:
        raise ApplicationError(404, "Open knowledge gap not found")
    db.add(AuditEvent(organization_id=member.organization_id, actor_id=member.user_id,
                      action="chatbot.gap_resolved", resource_type="knowledge_gap", resource_id=gap_id,
                      details={}))
    return _load_gap(db, member.organization_id, gap_id)
