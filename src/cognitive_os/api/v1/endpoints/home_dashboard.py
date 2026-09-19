from fastapi import APIRouter

from cognitive_os.api.dependencies import CaptureMember, Db
from cognitive_os.application.home_dashboard import home_summary
from cognitive_os.schemas.home_dashboard import HomeSummaryResponse

router = APIRouter(tags=["home-dashboard"])


@router.get("/dashboard/home", response_model=HomeSummaryResponse)
def home(db: Db, member: CaptureMember):
    return home_summary(db, member.organization_id)
