from uuid import UUID

from fastapi import APIRouter, Request
from openai import OpenAIError

from cognitive_os.api.dependencies import CaptureMember, Db, Member
from cognitive_os.application import policies
from cognitive_os.application.chatbot import log_query, record_gap
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_answer import OpenAIAnswerProvider
from cognitive_os.infrastructure.ai.openai_embeddings import OpenAIEmbeddingProvider
from cognitive_os.infrastructure.storage.azure_recordings import recording_store
from cognitive_os.schemas.policies import (
    PolicyAnswerResponse, PolicyCreate, PolicyQuestion, PolicyResponse, PolicySyncResult,
)
from cognitive_os.schemas.recordings import SignedTransfer

router = APIRouter(tags=["policies"])


@router.post("/policies", response_model=PolicyResponse, status_code=201)
def create(data: PolicyCreate, request: Request, db: Db, member: CaptureMember):
    return policies.create_policy(db, member, data, request.app.state.settings)


@router.get("/policies", response_model=list[PolicyResponse])
def index(db: Db, member: Member):
    return policies.list_policies(db, member)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
def get(policy_id: UUID, db: Db, member: Member):
    return policies.get_policy(db, member, policy_id)


@router.post("/policies/{policy_id}/upload-url", response_model=SignedTransfer)
def upload_url(policy_id: UUID, request: Request, db: Db, member: CaptureMember):
    item = policies.get_policy(db, member, policy_id, lock=True)
    if item.status != "uploading":
        raise ApplicationError(409, "Policy document is already uploaded")
    with recording_store(request.app.state.settings) as store:
        return store.transfer(item, write=True)


@router.post("/policies/{policy_id}/complete", response_model=PolicyResponse)
def complete(policy_id: UUID, request: Request, db: Db, member: CaptureMember):
    with recording_store(request.app.state.settings) as store:
        return policies.complete_policy(db, member, policy_id, store)


@router.get("/policies/{policy_id}/view", response_model=SignedTransfer)
def view(policy_id: UUID, request: Request, db: Db, member: Member):
    item = policies.get_policy(db, member, policy_id)
    if item.status == "uploading":
        raise ApplicationError(409, "Policy document is not uploaded yet")
    with recording_store(request.app.state.settings) as store:
        return store.transfer(item, write=False)


@router.post("/policies/{policy_id}/retry", response_model=PolicyResponse)
def retry(policy_id: UUID, db: Db, member: CaptureMember):
    return policies.retry_policy(db, member, policy_id)


@router.post("/policies/{policy_id}/retire", response_model=PolicyResponse)
def retire(policy_id: UUID, db: Db, member: CaptureMember):
    return policies.retire_policy(db, member, policy_id)


@router.post("/policies/sync", response_model=PolicySyncResult)
def sync(request: Request, db: Db, member: CaptureMember):
    settings = request.app.state.settings
    with recording_store(settings) as store:
        discovered = policies.sync_policies(db, member, store, settings.azure_storage_container,
                                            f"{member.organization_id}/policies/")
    return {"discovered": discovered}


@router.post("/policies/ask", response_model=PolicyAnswerResponse)
def ask(data: PolicyQuestion, request: Request, db: Db, member: Member):
    settings = request.app.state.settings
    embedding_provider = answer_provider = None
    try:
        embedding_provider = OpenAIEmbeddingProvider(settings)
        organization_id = member.organization_id
        # Release the read transaction before each potentially slow provider request.
        db.rollback()
        vector = embedding_provider.embed([data.question])[0]
        rows = policies.search_policy_vectors(db, organization_id, embedding_provider.model_name, vector,
                                              settings.chatbot_search_limit, data.policy_id)
        best_score = max((row["score"] for row in rows), default=None)
        if rows:
            db.rollback()
            answer_provider = OpenAIAnswerProvider(settings)
            decision = answer_provider.answer(data.question, rows)
            if decision.can_answer and decision.source_index is not None and decision.source_index < len(rows):
                chosen = rows[decision.source_index]
                citation = policies.build_policy_citation(chosen)
                log_query(db, member, embedding_provider.model_name, data.question, answered=True,
                         session_objective=citation["policy_title"], policy_id=citation["policy_id"])
                db.commit()
                return {"gap_detected": False, "answer": decision.answer, "citation": citation, "gap": None}
        gap = record_gap(db, member, embedding_provider.model_name, data.question, vector, best_score,
                         settings.knowledge_gap_dedup_similarity)
        log_query(db, member, embedding_provider.model_name, data.question, answered=False, gap_id=gap["id"])
        db.commit()
        return {"gap_detected": True, "answer": None, "citation": None, "gap": gap}
    except (ValueError, OpenAIError):
        raise ApplicationError(503, "Policy chatbot provider unavailable or not configured") from None
    finally:
        if embedding_provider:
            embedding_provider.close()
        if answer_provider:
            answer_provider.close()
