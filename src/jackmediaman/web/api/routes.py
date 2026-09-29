"""Main API router combining all endpoint modules."""

from fastapi import APIRouter

from .status import router as status_router
from .commands import router as commands_router
from .settings import router as settings_router

router = APIRouter()

# Include sub-routers
router.include_router(status_router, tags=["status"])
router.include_router(commands_router, prefix="/commands", tags=["commands"])
router.include_router(settings_router, prefix="/settings", tags=["settings"])
