from fastapi import APIRouter, Request
from openai import OpenAIError

from cognitive_os.api.dependencies import CaptureMember as Member, Db
from cognitive_os.application.search import unified_search
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
from cognitive_os.schemas.search import SearchQuery, SearchResult

router = APIRouter(tags=["search"])


@router.post("/search", response_model=list[SearchResult])
def search(data: SearchQuery, request: Request, db: Db, member: Member):
    provider = None
    try:
        provider = OpenAIEmbeddingProvider(request.app.state.settings)
        organization_id = member.organization_id
        # Release the read transaction before a potentially slow provider request.
        db.rollback()
        vector = provider.embed([data.query])[0]
        return unified_search(db, organization_id, provider.model_name, vector, data.query, data.limit)
    except (ValueError, OpenAIError):
        raise ApplicationError(503, "Semantic search provider unavailable or not configured") from None
    finally:
        if provider:
            provider.close()
