from fastapi import APIRouter, Request

from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.database.migrations import (
    REQUIRED_MIGRATIONS, SchemaUnavailable, missing_migrations)
from cognitive_os.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def ready(request: Request) -> ReadinessResponse:
    """Report whether the database is reachable and fully migrated.

    /health only proves the process is up. Without this check a database that is
    down or behind on migrations is only discovered as a 503 on a business
    request, with no indication of which migration is missing.
    """
    engine = request.app.state.engine
    if engine is None:
        raise ApplicationError(503, "Database is not configured; set COGNITIVE_DATABASE_URL")
    try:
        missing = missing_migrations(engine)
    except SchemaUnavailable as error:
        raise ApplicationError(503, error.detail) from None
    if missing:
        raise ApplicationError(503, "Missing migrations: " + ", ".join(missing))
    return ReadinessResponse(status="ready", migrations=list(REQUIRED_MIGRATIONS))
