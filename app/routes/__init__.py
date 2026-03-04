"""Route exports."""

from app.routes.admin import router as admin_router
from app.routes.health import router as health_router
from app.routes.oauth import router as oauth_router
from app.routes.slack import router as slack_router
from app.routes.zoom import router as zoom_router

__all__ = [
    "admin_router",
    "health_router",
    "oauth_router",
    "slack_router",
    "zoom_router",
]
