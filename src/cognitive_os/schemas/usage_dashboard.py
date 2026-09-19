from datetime import date, datetime

from pydantic import BaseModel


class DailyCount(BaseModel):
    day: date
    total: int


class TopQuestion(BaseModel):
    topic: str
    total: int


class UsageSummaryResponse(BaseModel):
    since: datetime
    questions: int
    answered: int
    coverage: float | None
    answered_today: int
    open_gaps: int
    per_day: list[DailyCount]
    top_questions: list[TopQuestion]
