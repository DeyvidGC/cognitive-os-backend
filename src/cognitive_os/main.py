from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, ProgrammingError

from cognitive_os.api.v1.router import api_router
from cognitive_os.core.config import Settings
from cognitive_os.domain.errors import ApplicationError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = None
        if settings.database_url:
            engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                                   hide_parameters=True, connect_args={"connect_timeout": 5})
        application.state.engine = engine
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.engine = None
    application.include_router(api_router, prefix="/api/v1")

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
        return JSONResponse(status_code=503, content={"detail": "Database unavailable or migrations missing"})

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": "Hello World"}

    @application.get("/hello/{name}", include_in_schema=False)
    async def say_hello(name: str) -> dict[str, str]:
        return {"message": f"Hello {name}"}

    return application


app = create_app()
