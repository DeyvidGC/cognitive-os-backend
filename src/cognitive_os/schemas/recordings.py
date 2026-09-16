from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecordingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    media_type: Literal["video/webm", "video/mp4"]
    size_bytes: int = Field(gt=0)
    consent: Literal[True]
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    audio_consent: bool = False

    @field_validator("media_type", mode="before")
    @classmethod
    def normalize_media_type(cls, value):
        return value.split(";", 1)[0].strip().lower() if isinstance(value, str) else value


class RecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    session_id: UUID
    media_type: str
    size_bytes: int
    content_sha256: str | None
    audio_consent: bool
    status: str
    created_at: datetime
    uploaded_at: datetime | None
    error_code: str | None


class SignedTransfer(BaseModel):
    url: str
    expires_at: datetime
    method: Literal["PUT", "GET"]
    headers: dict[str, str]


class VisualInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1, max_length=4000)
    expected_result: str = Field(min_length=1, max_length=2000)
    frame_indices: list[int] = Field(max_length=61)
    text_sources: list[Literal["transcript", "notes", "clarifications"]] = Field(default_factory=list)


class VisualReportContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    report: str = Field(min_length=1, max_length=16000)
    instructions: list[VisualInstruction] = Field(max_length=50)
    uncertainties: list[str] = Field(max_length=30)
    questions: list[str] = Field(default_factory=list, max_length=10)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recording_id: UUID
    content: VisualReportContent
    sampling: dict
    model_name: str
    prompt_version: str
    revision: int
    review_status: str
    reviewer_id: UUID | None
    reviewed_at: datetime | None
    feedback: str | None
    version_id: UUID | None


class ReportRegenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)


class ReportEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    content: VisualReportContent


class ReportReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    decision: Literal["approved", "rejected"]
    feedback: str = Field(default="", max_length=4000)
