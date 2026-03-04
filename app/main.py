"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.config import settings
from app.middlewares import (
    AppError,
    RequestMiddleware,
    app_error_handler,
    generic_error_handler,
    validation_error_handler,
)
from app.routes import admin_router, health_router, oauth_router, slack_router, zoom_router
from app.services import queue_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Args:
        app: FastAPI application

    Yields:
        None
    """
    # Startup
    logger.info(
        "Starting AI Meeting Bot",
        environment=settings.environment,
        port=settings.port,
    )

    # Start background queue
    await queue_service.start()

    # Register queue handlers
    from app.services import meeting_service

    async def process_recording_handler(data: dict) -> dict:
        from app.models.types import ZoomWebhookPayload

        payload = ZoomWebhookPayload(**data)
        return await meeting_service.process_recording_completed(payload)

    queue_service.register_handler("process_recording", process_recording_handler)

    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down AI Meeting Bot")
    await queue_service.stop()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="AI Meeting Operations Bot",
        description="Automates meeting processing with AI-powered summarization and integrations",
        version="1.0.0",
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url="/api/redoc" if settings.environment != "production" else None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request logging middleware
    app.add_middleware(RequestMiddleware)

    # Register exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # Register routes
    app.include_router(health_router, prefix="/api")
    app.include_router(zoom_router, prefix="/api")
    app.include_router(slack_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(oauth_router, prefix="/api")

    # Root endpoint
    @app.get("/")
    async def root() -> dict:
        return {
            "name": "AI Meeting Operations Bot",
            "version": "1.0.0",
            "status": "running",
            "slack_events_url": "/api/slack/events",
            "docs": "/docs",
        }

    @app.post("/")
    async def root_post(request: Request) -> Response:
        """Handle POST to root - might be Slack challenge sent to wrong URL."""
        from fastapi.responses import JSONResponse
        try:
            body = await request.json()
            
            # Check if this is a Slack URL verification sent to wrong endpoint
            if body.get("type") == "url_verification":
                challenge = body.get("challenge")
                logger.warning(
                    "Slack challenge received at root - correct URL is /api/slack/events"
                )
                # Return the challenge anyway to help during setup
                return JSONResponse(
                    content={"challenge": challenge},
                    media_type="application/json"
                )
        except Exception:
            pass
        
        return JSONResponse(
            status_code=400,
            content={
                "error": "Use /api/slack/events for Slack events",
                "correct_url": "/api/slack/events"
            }
        )

    logger.info("Application created", environment=settings.environment)

    return app


# Application instance
app = create_app()
