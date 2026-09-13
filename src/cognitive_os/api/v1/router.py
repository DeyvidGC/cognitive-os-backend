from fastapi import APIRouter

from cognitive_os.api.v1.endpoints.health import router as health_router
from cognitive_os.api.v1.endpoints.auth import router as auth_router
from cognitive_os.api.v1.endpoints.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(sessions_router)
