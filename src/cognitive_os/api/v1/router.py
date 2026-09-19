from fastapi import APIRouter

from cognitive_os.api.v1.endpoints.health import router as health_router
from cognitive_os.api.v1.endpoints.auth import router as auth_router
from cognitive_os.api.v1.endpoints.sessions import router as sessions_router
from cognitive_os.api.v1.endpoints.procedures import router as procedures_router
from cognitive_os.api.v1.endpoints.evidence import router as evidence_router
from cognitive_os.api.v1.endpoints.clarifications import router as clarifications_router
from cognitive_os.api.v1.endpoints.recordings import router as recordings_router
from cognitive_os.api.v1.endpoints.agent import router as agent_router
from cognitive_os.api.v1.endpoints.recording_knowledge import router as recording_knowledge_router
from cognitive_os.api.v1.endpoints.chatbot import router as chatbot_router
from cognitive_os.api.v1.endpoints.usage_dashboard import router as usage_dashboard_router
from cognitive_os.api.v1.endpoints.policies import router as policies_router
from cognitive_os.api.v1.endpoints.change_proposals import router as change_proposals_router
from cognitive_os.api.v1.endpoints.master import router as master_router
from cognitive_os.api.v1.endpoints.home_dashboard import router as home_dashboard_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(sessions_router)
api_router.include_router(procedures_router)
api_router.include_router(evidence_router)
api_router.include_router(clarifications_router)
api_router.include_router(recordings_router)
api_router.include_router(agent_router)
api_router.include_router(recording_knowledge_router)
api_router.include_router(chatbot_router)
api_router.include_router(usage_dashboard_router)
api_router.include_router(policies_router)
api_router.include_router(change_proposals_router)
api_router.include_router(master_router)
api_router.include_router(home_dashboard_router)
