from fastapi import APIRouter, Query, Request
from openai import OpenAIError

from cognitive_os.api.dependencies import Db, PlatformStaff
from cognitive_os.application import master
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_answer import OpenAIAnswerProvider
from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
from cognitive_os.schemas.master import MasterAnswerEntry, MasterQuestion, MasterUsageEntry, OrganizationSummary

router = APIRouter(tags=["master"])


@router.get("/master/organizations", response_model=list[OrganizationSummary])
def organizations(db: Db, staff: PlatformStaff):
    return master.list_organizations(db)


@router.get("/master/usage", response_model=list[MasterUsageEntry])
def usage(db: Db, staff: PlatformStaff, days: int = Query(default=7, ge=1, le=90)):
    return master.compare_usage(db, days)


@router.post("/master/chatbot/ask", response_model=list[MasterAnswerEntry])
def ask(data: MasterQuestion, request: Request, db: Db, staff: PlatformStaff):
    return _compare(request, db, master.compare_answers, data.question)


@router.post("/master/policies/ask", response_model=list[MasterAnswerEntry])
def ask_policies(data: MasterQuestion, request: Request, db: Db, staff: PlatformStaff):
    return _compare(request, db, master.compare_policy_answers, data.question)


def _compare(request, db, compare, question):
    settings = request.app.state.settings
    embedding_provider = answer_provider = None
    try:
        embedding_provider = OpenAIEmbeddingProvider(settings)
        db.rollback()
        answer_provider = OpenAIAnswerProvider(settings)
        return compare(db, settings, question, embedding_provider, answer_provider)
    except (ValueError, OpenAIError):
        raise ApplicationError(503, "Chatbot provider unavailable or not configured") from None
    finally:
        if embedding_provider:
            embedding_provider.close()
        if answer_provider:
            answer_provider.close()
