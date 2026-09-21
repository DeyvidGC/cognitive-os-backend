from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1200)
    limit: int = Field(default=10, ge=1, le=20)


class SearchResult(BaseModel):
    type: Literal["video", "procedure"]
    score: float
    snippet: str
    timestamp_ms: int | None = None
    recording_id: UUID | None = None
    session_id: UUID | None = None
    procedure_id: UUID | None = None
    version_id: UUID | None = None
    step_id: UUID | None = None
