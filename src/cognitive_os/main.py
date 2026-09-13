from fastapi import FastAPI

from cognitive_os.api.v1.router import api_router
from cognitive_os.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    application = FastAPI(title=settings.app_name, version="0.1.0")
    application.state.settings = settings
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": "Hello World"}

    @application.get("/hello/{name}", include_in_schema=False)
    async def say_hello(name: str) -> dict[str, str]:
        return {"message": f"Hello {name}"}

    return application


app = create_app()
