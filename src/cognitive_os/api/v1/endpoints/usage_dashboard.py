from fastapi import APIRouter, Query

from cognitive_os.api.dependencies import CaptureMember, Db
from cognitive_os.application.usage_dashboard import summary
from cognitive_os.schemas.usage_dashboard import UsageSummaryResponse

router = APIRouter(tags=["usage-dashboard"])


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def usage_summary(db: Db, member: CaptureMember, days: int = Query(default=7, ge=1, le=90)):
    return summary(db, member.organization_id, days)
