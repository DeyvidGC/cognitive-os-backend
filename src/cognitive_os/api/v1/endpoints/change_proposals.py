from uuid import UUID

from fastapi import APIRouter, Request
from openai import OpenAIError

from cognitive_os.api.dependencies import CaptureMember, Db, Member
from cognitive_os.application.change_proposals import apply_proposal, discard_proposal, list_proposals, propose_change
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.ai.openai_change import OpenAIChangeProvider
from cognitive_os.schemas.change_proposals import ChangeProposalResponse, ChangeRequest
from cognitive_os.schemas.procedures import VersionResponse

router = APIRouter(tags=["change-proposals"])


@router.post("/procedure-versions/{version_id}/change-proposals", response_model=ChangeProposalResponse,
             status_code=201)
def propose(version_id: UUID, data: ChangeRequest, request: Request, db: Db, member: CaptureMember):
    provider = None
    try:
        provider = OpenAIChangeProvider(request.app.state.settings)
        return propose_change(db, member, version_id, data.request_text, provider)
    except (ValueError, OpenAIError):
        raise ApplicationError(503, "Change proposal provider unavailable or not configured") from None
    finally:
        if provider:
            provider.close()


@router.get("/procedure-versions/{version_id}/change-proposals", response_model=list[ChangeProposalResponse])
def index(version_id: UUID, db: Db, member: Member):
    return list_proposals(db, member, version_id)


@router.post("/change-proposals/{proposal_id}/apply", response_model=VersionResponse)
def apply(proposal_id: UUID, db: Db, member: CaptureMember):
    return apply_proposal(db, member, proposal_id)


@router.post("/change-proposals/{proposal_id}/discard", response_model=ChangeProposalResponse)
def discard(proposal_id: UUID, db: Db, member: CaptureMember):
    return discard_proposal(db, member, proposal_id)
