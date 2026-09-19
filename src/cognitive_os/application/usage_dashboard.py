"""Usage metrics derived from cognitive.chat_queries and cognitive.knowledge_gaps.
Read-only aggregation; never writes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text


def summary(db, organization_id, days=7):
    since = datetime.now(UTC) - timedelta(days=days)
    total, answered = db.execute(text("""SELECT count(*), count(*) FILTER (WHERE answered)
        FROM cognitive.chat_queries WHERE organization_id=:org AND created_at >= :since"""),
        {"org": organization_id, "since": since}).one()
    answered_today = db.scalar(text("""SELECT count(*) FROM cognitive.chat_queries
        WHERE organization_id=:org AND answered AND created_at >= date_trunc('day', now())"""),
        {"org": organization_id})
    open_gaps = db.scalar(text("""SELECT count(*) FROM cognitive.knowledge_gaps
        WHERE organization_id=:org AND status='open'"""), {"org": organization_id})
    per_day = db.execute(text("""SELECT date_trunc('day', created_at) AS day, count(*) AS total
        FROM cognitive.chat_queries WHERE organization_id=:org AND created_at >= :since
        GROUP BY 1 ORDER BY 1"""), {"org": organization_id, "since": since}).mappings().all()
    top = db.execute(text("""SELECT session_objective, count(*) AS total FROM cognitive.chat_queries
        WHERE organization_id=:org AND answered AND session_objective IS NOT NULL AND created_at >= :since
        GROUP BY session_objective ORDER BY total DESC LIMIT 5"""),
        {"org": organization_id, "since": since}).mappings().all()
    return {
        "since": since,
        "questions": total,
        "answered": answered,
        "coverage": round(answered / total, 4) if total else None,
        "answered_today": answered_today,
        "open_gaps": open_gaps,
        "per_day": [{"day": row["day"].date(), "total": row["total"]} for row in per_day],
        "top_questions": [{"topic": row["session_objective"], "total": row["total"]} for row in top],
    }
