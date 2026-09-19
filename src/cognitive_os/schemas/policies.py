from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cognitive_os.schemas.chatbot import KnowledgeGapResponse


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    size_bytes: int = Field(gt=0)
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    title: str = Field(default="", max_length=200)


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str = ""
    source: str
    size_bytes: int
    status: str
    error_code: str | None
    created_at: datetime
    analyzed_at: datetime | None


class PolicySyncResult(BaseModel):
    discovered: int


class PolicyQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1200)
    policy_id: UUID | None = None


class PolicyCitation(BaseModel):
    policy_id: UUID
    policy_title: str
    label: str
    score: float


class PolicyAnswerResponse(BaseModel):
    gap_detected: bool
    answer: str | None = None
    citation: PolicyCitation | None = None
    gap: KnowledgeGapResponse | None = None
