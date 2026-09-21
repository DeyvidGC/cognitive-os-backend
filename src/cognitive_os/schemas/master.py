from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cognitive_os.schemas.usage_dashboard import UsageSummaryResponse


class OrganizationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


class MasterUsageEntry(UsageSummaryResponse):
    organization_id: UUID
    organization_name: str
    topics: list[str]


class MasterQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1200)


class MasterAnswerEntry(BaseModel):
    organization_id: UUID
    organization_name: str
    answer: str | None
