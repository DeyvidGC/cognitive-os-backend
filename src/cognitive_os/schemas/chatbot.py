from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1200)


class Citation(BaseModel):
    recording_id: UUID
    session_objective: str | None
    label: str
    score: float


class KnowledgeGapResponse(BaseModel):
    id: UUID
    question: str
    asked_count: int
    status: str
    best_score: float | None
    created_at: datetime
    last_asked_at: datetime


class ChatAnswerResponse(BaseModel):
    gap_detected: bool
    answer: str | None = None
    citation: Citation | None = None
    gap: KnowledgeGapResponse | None = None


class ChatHistoryEntry(BaseModel):
    id: UUID
    question: str
    answered: bool
    session_objective: str | None
    recording_id: UUID | None
    policy_id: UUID | None
    created_at: datetime
