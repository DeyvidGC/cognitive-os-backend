import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from cognitive_os.api.v1.router import api_router
from cognitive_os.core.config import Settings
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.core.rate_limit import AuthRateLimiter
from cognitive_os.infrastructure.database.migrations import SchemaUnavailable, missing_migrations

logger = logging.getLogger(__name__)


def log_database_error(request: Request, exc: Exception) -> None:
    """Record why a database call failed, since the response never says.

    A 503 reads the same whether PostgreSQL is down, a migration is missing or
    the API role lacks a grant on one table, so without this the only way to tell
    is to rerun the query by hand. The engine sets hide_parameters, so the
    statement is logged without its bound values.
    """
    cause = getattr(exc, "orig", None) or exc
    logger.error("Database error on %s %s: %s: %s", request.method, request.url.path,
                 type(cause).__name__, cause)


def report_schema_state(engine: Engine) -> None:
    """Log pending migrations at startup instead of failing per request later.

    Startup keeps going: documentation and /health stay reachable, and
    /health/ready reports the same detail to whoever calls the API.
    """
    try:
        missing = missing_migrations(engine)
    except SchemaUnavailable as error:
        logger.error("Database not ready: %s", error.detail)
        return
    if missing:
        logger.error("Database is missing migrations: %s. Apply them from migrations/ "
                     "before using the API; see GET /api/v1/health/ready.", ", ".join(missing))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = None
        if settings.database_url:
            engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                                   hide_parameters=True, connect_args={"connect_timeout": 5})
            report_schema_state(engine)
        application.state.engine = engine
        workers = None
        try:
            if settings.embedded_workers:
                from cognitive_os.workers.runtime import LocalWorkers
                workers = LocalWorkers(settings)
                application.state.workers = workers
                workers.start()
            yield
        finally:
            if workers is not None:
                workers.close()
            if engine is not None:
                engine.dispose()

    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    if settings.cors_origins:
        application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                                   allow_methods=["GET", "POST", "PUT", "OPTIONS"],
                                   allow_headers=["Authorization", "Content-Type", "X-Organization-ID"],
                                   allow_credentials=False)
    application.state.settings = settings
    application.state.engine = None
    application.state.workers = None
    application.state.auth_limiter = AuthRateLimiter()
    application.include_router(api_router, prefix="/api/v1")

    @application.middleware("http")
    async def limit_auth_requests(request: Request, call_next):
        if request.method == "POST" and request.url.path.rstrip("/") in {
            "/api/v1/auth/register", "/api/v1/auth/login"
        }:
            client = request.client.host if request.client else "unknown"
            if not application.state.auth_limiter.allow(client):
                return JSONResponse(status_code=429, content={"detail": "Too many authentication attempts"},
                                    headers={"Retry-After": "60", "Cache-Control": "no-store"})
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError):
        headers = {"Cache-Control": "no-store"}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # FastAPI's default response echoes input, which can contain passwords.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                  for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @application.exception_handler(OperationalError)
    @application.exception_handler(ProgrammingError)
    async def database_error(request: Request, exc: Exception):
        # The body stays generic: "permission denied for table x" or a column name
        # would describe the schema to any caller. The cause goes to the log, which
        # is otherwise the one place the reason for a 503 is lost.
        log_database_error(request, exc)
        return JSONResponse(status_code=503, content={"detail": "Database unavailable or migrations missing"})

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        log_database_error(request, exc)
        return JSONResponse(status_code=409, content={"detail": "Resource conflicts with existing data"})

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": "Hello World"}

    @application.get("/hello/{name}", include_in_schema=False)
    async def say_hello(name: str) -> dict[str, str]:
        return {"message": f"Hello {name}"}

    return application
