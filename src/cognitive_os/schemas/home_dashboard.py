from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActiveSession(BaseModel):
    id: UUID
    objective: str
    application_name: str
    status: str
    author_name: str


class ActivityEntry(BaseModel):
    id: UUID
    actor_name: str
    action: str
    label: str
    resource_type: str
    resource_id: UUID
    details: dict
    created_at: datetime


class HomeSummaryResponse(BaseModel):
    answered_today: int
    coverage: float | None
    open_gaps: int
    active_sessions: list[ActiveSession]
    recent_activity: list[ActivityEntry]
