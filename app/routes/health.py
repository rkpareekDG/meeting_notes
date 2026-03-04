"""Health check routes."""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.services import queue_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str
    environment: str


class DetailedHealthResponse(HealthResponse):
    """Detailed health check response."""

    services: dict[str, dict[str, Any]]
    queue_stats: dict[str, int]


@router.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API info.

    Returns:
        API information
    """
    return {
        "name": "AI Meeting Bot",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "slack_events": "/api/slack/events",
            "slack_interactions": "/api/slack/interactions",
            "zoom_webhook": "/api/zoom/webhook",
            "oauth_status": "/api/oauth/status/{user_id}",
            "health": "/api/health",
        },
        "docs": "/docs",
    }


@router.post("/")
async def root_post(request: Request) -> JSONResponse:
    """Handle POST to root - might be Slack challenge sent to wrong URL.

    Returns:
        Helpful error or challenge response
    """
    try:
        body = await request.json()
        
        # Check if this is a Slack URL verification sent to wrong endpoint
        if body.get("type") == "url_verification":
            challenge = body.get("challenge")
            logger.warning(
                "Slack challenge received at root - URL should be /api/slack/events",
                challenge=challenge[:20] if challenge else None
            )
            # Return the challenge anyway to help user verify it works
            return JSONResponse(
                content={"challenge": challenge},
                media_type="application/json"
            )
    except Exception:
        pass
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid endpoint",
            "message": "Slack events should be sent to /api/slack/events",
            "correct_url": "https://your-domain.com/api/slack/events"
        }
    )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check.

    Returns:
        Health status
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        environment=settings.environment,
    )


@router.get("/health/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """Kubernetes liveness probe.

    Returns:
        Liveness status
    """
    return HealthResponse(
        status="alive",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        environment=settings.environment,
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """Kubernetes readiness probe.

    Returns:
        Readiness status
    """
    # Add checks for dependencies here
    # For now, always return ready
    return HealthResponse(
        status="ready",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        environment=settings.environment,
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check() -> DetailedHealthResponse:
    """Detailed health check with service status.

    Returns:
        Detailed health status
    """
    services: dict[str, dict[str, Any]] = {
        "zoom": {
            "configured": bool(settings.zoom_client_id),
            "status": "unknown",
        },
        "slack": {
            "configured": bool(settings.slack_bot_token),
            "status": "unknown",
        },
        "openai": {
            "configured": bool(settings.openai_api_key),
            "status": "unknown",
        },
        "jira": {
            "configured": bool(settings.jira_api_token),
            "status": "unknown",
        },
        "microsoft": {
            "configured": bool(settings.microsoft_client_id),
            "status": "unknown",
        },
    }

    queue_stats = queue_service.get_stats()

    return DetailedHealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        environment=settings.environment,
        services=services,
        queue_stats=queue_stats,
    )
