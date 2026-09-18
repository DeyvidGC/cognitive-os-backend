from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["auth"]
    token: str = Field(min_length=1, max_length=1000, repr=False)
    organization_id: UUID
    consent: Literal[True]


class AgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["observe", "message"]
    message_id: UUID
    text: str = Field(default="", max_length=5000)
    image_base64: str | None = Field(default=None, max_length=700000, repr=False)
    offset_ms: int = Field(default=0, ge=0, le=1800000)
    clarification_id: UUID | None = None

    @model_validator(mode="after")
    def needs_input(self):
        if not self.text.strip() and not self.image_base64:
            raise ValueError("Supply text or a screenshot")
        return self


class AgentReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation: str = Field(max_length=3000)
    answer: str = Field(max_length=3000)
    questions: list[str] = Field(max_length=5)
