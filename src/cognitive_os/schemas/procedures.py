from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cognitive_os.schemas.auth import Name


class ProcedureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Name
    scope: str = Field(min_length=1, max_length=4000)


class ProcedureResponse(ProcedureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    created_at: datetime


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(default="", max_length=10000)
    source_session_id: UUID | None = None


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    procedure_id: UUID
    source_session_id: UUID | None
    version_number: int
    status: str
    summary: str
    reviewer_id: UUID | None
    approved_at: datetime | None
    published_at: datetime | None
    created_at: datetime


class StepWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    position: int = Field(ge=1, le=10000)
    instruction: str = Field(min_length=1, max_length=10000)
    expected_result: str = Field(min_length=1, max_length=10000)
    origin: Literal["observed", "user_explained", "inferred"]
    validation_status: Literal["pending", "confirmed", "rejected"] = "pending"


class StepResponse(StepWrite):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_id: UUID


class StepReorder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_ids: list[UUID] = Field(min_length=1, max_length=10000)


class TutorialWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=100000)


class TutorialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_id: UUID
    format: str
    content: str | None
    created_at: datetime


class KnowledgeResult(BaseModel):
    id: UUID
    procedure_id: UUID
    version_id: UUID
    version_number: int
    step_id: UUID | None
    content: str
    rank: float
