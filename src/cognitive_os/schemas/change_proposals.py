from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_text: str = Field(min_length=1, max_length=1000)


class ChangeProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_id: UUID
    procedure_id: UUID
    request_text: str
    kind: str
    after_position: int
    step_position: int | None
    instruction: str
    expected_result: str
    rationale: str
    status: str
    applied_version_id: UUID | None
    created_at: datetime
