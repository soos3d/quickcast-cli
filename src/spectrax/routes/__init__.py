"""Route modules for the video feed API."""

from fastapi import APIRouter

# Import all route modules
from .video import router as video_router
from .pages import router as pages_router
from .files import router as files_router
from .recordings import router as recordings_router
from .statistics import router as statistics_router
from .auth import router as auth_router

# Export all routers
__all__ = [
    "video_router",
    "pages_router", 
    "files_router",
    "recordings_router",
    "statistics_router",
    "auth_router"
]
