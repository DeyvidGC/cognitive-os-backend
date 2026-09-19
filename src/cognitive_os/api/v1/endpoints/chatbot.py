from uuid import UUID

from fastapi import APIRouter, Query, Request
from openai import OpenAIError

from cognitive_os.api.dependencies import CaptureMember, Db, Member
from cognitive_os.application.chatbot import build_citation, history, list_gaps, log_query, record_gap, resolve_gap
from cognitive_os.application.recording_knowledge import search_vectors
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_answer import OpenAIAnswerProvider
from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
from cognitive_os.schemas.chatbot import ChatAnswerResponse, ChatHistoryEntry, ChatQuestion, KnowledgeGapResponse

router = APIRouter(tags=["chatbot"])


@router.post("/chatbot/ask", response_model=ChatAnswerResponse)
def ask(data: ChatQuestion, request: Request, db: Db, member: Member):
    settings = request.app.state.settings
    embedding_provider = answer_provider = None
    try:
        embedding_provider = OpenAIEmbeddingProvider(settings)
        organization_id = member.organization_id
        # Release the read transaction before each potentially slow provider request.
        db.rollback()
        vector = embedding_provider.embed([data.question])[0]
        rows = search_vectors(db, organization_id, embedding_provider.model_name, vector,
                              settings.chatbot_search_limit)
        best_score = max((row["score"] for row in rows), default=None)
        if rows:
            db.rollback()
            answer_provider = OpenAIAnswerProvider(settings)
            decision = answer_provider.answer(data.question, rows)
            if decision.can_answer and decision.source_index is not None and decision.source_index < len(rows):
                citation = build_citation(db, organization_id, rows[decision.source_index])
                log_query(db, member, embedding_provider.model_name, data.question, answered=True,
                         session_objective=citation["session_objective"], recording_id=citation["recording_id"])
                db.commit()
                return {"gap_detected": False, "answer": decision.answer, "citation": citation, "gap": None}
        gap = record_gap(db, member, embedding_provider.model_name, data.question, vector, best_score,
                         settings.knowledge_gap_dedup_similarity)
        log_query(db, member, embedding_provider.model_name, data.question, answered=False, gap_id=gap["id"])
        db.commit()
        return {"gap_detected": True, "answer": None, "citation": None, "gap": gap}
    except (ValueError, OpenAIError):
        raise ApplicationError(503, "Chatbot provider unavailable or not configured") from None
    finally:
        if embedding_provider:
            embedding_provider.close()
        if answer_provider:
            answer_provider.close()


@router.get("/chatbot/history", response_model=list[ChatHistoryEntry])
def chat_history(db: Db, member: Member, limit: int = Query(default=20, ge=1, le=100)):
    return history(db, member, limit)


@router.get("/chatbot/gaps", response_model=list[KnowledgeGapResponse])
def gaps(db: Db, member: Member):
    return list_gaps(db, member)


@router.post("/chatbot/gaps/{gap_id}/resolve", response_model=KnowledgeGapResponse)
def resolve(gap_id: UUID, db: Db, member: CaptureMember):
    gap = resolve_gap(db, member, gap_id)
    db.commit()
    return gap
