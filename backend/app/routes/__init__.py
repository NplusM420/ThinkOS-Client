from fastapi import APIRouter

from .auth import router as auth_router
from .memories import router as memories_router
from .chat import router as chat_router
from .settings import router as settings_router
from .conversations import router as conversations_router
from .jobs import router as jobs_router
from .tools import router as tools_router
from .agents import router as agents_router
from .secrets import router as secrets_router
from .workflows import router as workflows_router
from .voice import router as voice_router
from .graph import router as graph_router
from .plugins import router as plugins_router
from .inbox import router as inbox_router
from .websocket import router as websocket_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(memories_router)
router.include_router(chat_router)
router.include_router(settings_router)
router.include_router(conversations_router)
router.include_router(jobs_router)
router.include_router(tools_router)
router.include_router(agents_router)
router.include_router(secrets_router)
router.include_router(workflows_router)
router.include_router(voice_router)
router.include_router(graph_router)
router.include_router(plugins_router)
router.include_router(inbox_router)
router.include_router(websocket_router)
