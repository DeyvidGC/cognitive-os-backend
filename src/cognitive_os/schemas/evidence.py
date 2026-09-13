from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    session_id: UUID
    media_type: str
    size_bytes: int
    sha256: str
    captured_at: datetime


class EvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    evidence_id: UUID
    explanation: str = Field(min_length=1, max_length=4000)


class ClarificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)


class ClarificationAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    answer: str = Field(min_length=1, max_length=10000)


class ClarificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    session_id: UUID
    question: str
    answer: str | None
    answered_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime
