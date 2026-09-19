"""Cross-organization comparison for Inventiva platform staff only. Every
function here deliberately takes an organization_id instead of a Member, and
never writes: master mode never leaves a trace inside a client's own usage
stats or knowledge-gap board, it only reads what already exists there.
"""

from sqlalchemy import select

from cognitive_os.application.policies import search_policy_vectors
from cognitive_os.application.recording_knowledge import search_vectors
from cognitive_os.application.usage_dashboard import summary as usage_summary
from cognitive_os.infrastructure.database.models import Organization


def list_organizations(db):
    return db.scalars(select(Organization).order_by(Organization.name)).all()


def compare_usage(db, days=7):
    return [{"organization_id": org.id, "organization_name": org.name,
             **usage_summary(db, org.id, days)} for org in list_organizations(db)]


def _compare(db, settings, question, embedding_provider, answer_provider, search):
    vector = embedding_provider.embed([question])[0]
    results = []
    for org in list_organizations(db):
        rows = search(org.id, vector)
        answer = None
        if rows:
            decision = answer_provider.answer(question, rows)
            if decision.can_answer and decision.source_index is not None and decision.source_index < len(rows):
                answer = decision.answer
        results.append({"organization_id": org.id, "organization_name": org.name, "answer": answer})
    return results


def compare_answers(db, settings, question, embedding_provider, answer_provider):
    return _compare(db, settings, question, embedding_provider, answer_provider,
                    lambda org_id, vector: search_vectors(
                        db, org_id, embedding_provider.model_name, vector, settings.chatbot_search_limit))


def compare_policy_answers(db, settings, question, embedding_provider, answer_provider):
    return _compare(db, settings, question, embedding_provider, answer_provider,
                    lambda org_id, vector: search_policy_vectors(
                        db, org_id, embedding_provider.model_name, vector, settings.chatbot_search_limit))
