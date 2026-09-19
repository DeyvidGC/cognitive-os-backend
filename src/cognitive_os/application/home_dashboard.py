"""Aggregates the handful of live numbers the Inicio screen needs: today's
top-line usage (via usage_dashboard) plus which learning sessions are
currently active, with the author's name resolved for display.
"""

from sqlalchemy import select

from cognitive_os.application.usage_dashboard import summary as usage_summary
from cognitive_os.infrastructure.database.models import AuditEvent, LearningSession, User

# Spanish label for each action code emitted via AuditEvent across the app.
# Falls back to the raw code for anything not listed here.
_ACTION_LABELS = {
    "ai.draft_created": "generó un borrador de procedimiento",
    "recording.report_generated": "generó el informe de una grabación",
    "recording.report_reviewed": "revisó el informe de una grabación",
    "recording.report_edited": "editó el informe de una grabación",
    "recording.converted": "convirtió una grabación en procedimiento",
    "version.created": "creó una nueva versión de procedimiento",
    "step.created": "agregó un paso",
    "step.updated": "actualizó un paso",
    "version.submit": "envió una versión a revisión",
    "version.approve": "aprobó una versión",
    "version.return": "devolvió una versión a borrador",
    "version.retire": "retiró una versión",
    "version.published": "publicó una nueva versión",
    "version.superseded": "quedó reemplazada por una nueva versión",
    "tutorial.updated": "actualizó un tutorial",
    "chatbot.gap_detected": "el chatbot detectó un vacío de conocimiento",
    "chatbot.gap_resolved": "resolvió un vacío de conocimiento",
    "change_proposal.applied": "aplicó una propuesta de cambio",
}


def active_sessions(db, organization_id):
    rows = db.execute(select(LearningSession, User).join(
        User, User.id == LearningSession.author_id).where(
        LearningSession.organization_id == organization_id,
        LearningSession.status.in_(("capturing", "processing")),
    ).order_by(LearningSession.created_at.desc())).all()
    return [{"id": session.id, "objective": session.objective, "application_name": session.application_name,
             "status": session.status, "author_name": user.display_name} for session, user in rows]


def recent_activity(db, organization_id, limit=10):
    # actor_id is null for system/worker-emitted events (e.g. the curator or a
    # background job), which the design shows with an "IA" badge instead of a name.
    rows = db.execute(select(AuditEvent, User).outerjoin(
        User, User.id == AuditEvent.actor_id).where(
        AuditEvent.organization_id == organization_id,
    ).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": event.id, "actor_name": user.display_name if user else "Cognitive IA",
             "action": event.action, "label": _ACTION_LABELS.get(event.action, event.action),
             "resource_type": event.resource_type, "resource_id": event.resource_id,
             "details": event.details, "created_at": event.created_at} for event, user in rows]


def home_summary(db, organization_id, days=30):
    usage = usage_summary(db, organization_id, days)
    return {"answered_today": usage["answered_today"], "coverage": usage["coverage"],
            "open_gaps": usage["open_gaps"], "active_sessions": active_sessions(db, organization_id),
            "recent_activity": recent_activity(db, organization_id)}
