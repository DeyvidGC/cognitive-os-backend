from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cognitive_os.schemas.auth import Name


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    objective: str = Field(min_length=1, max_length=4000)
    application_name: Name
    consent: Literal[True]


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    author_id: UUID
    objective: str
    application_name: str
    status: str
    consent_at: datetime
    created_at: datetime
    finished_at: datetime | None


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    idempotency_key: str = Field(min_length=1, max_length=200)
    sequence_number: int = Field(ge=0, le=2**63 - 1)
    offset_ms: int = Field(ge=0, le=2**63 - 1)
    event_type: Literal["message", "transcript"]
    text: str = Field(min_length=1, max_length=20000)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    session_id: UUID
    sequence_number: int
    idempotency_key: str
    event_type: str
    offset_ms: int
    payload: dict
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    session_id: UUID | None
    version_id: UUID | None
    recording_id: UUID | None
    kind: str
    status: str
    stage: str
    progress_percent: int
    last_error: str | None
    available_at: datetime
    max_attempts: int
    attempts: int
    created_at: datetime
    completed_at: datetime | None
