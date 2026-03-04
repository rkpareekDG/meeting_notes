"""Slack request signature verification middleware."""

import json
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from app.config import settings
from app.services.slack import slack_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SlackAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for verifying Slack request signatures."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and verify Slack signature for interaction routes.

        Args:
            request: Incoming request
            call_next: Next handler

        Returns:
            Response
        """
        # Only apply to Slack routes
        if not request.url.path.startswith("/api/slack"):
            return await call_next(request)

        # Read body once
        body = await request.body()
        
        # Handle URL verification challenge - respond immediately
        # This is needed during Slack app setup before signing secret might work
        if request.url.path.endswith("/events"):
            try:
                body_json = json.loads(body)
                if body_json.get("type") == "url_verification":
                    challenge = body_json.get("challenge")
                    logger.info("Slack URL verification challenge received in middleware")
                    return JSONResponse(
                        content={"challenge": challenge},
                        media_type="application/json"
                    )
            except (json.JSONDecodeError, Exception):
                pass  # Not a JSON body or not a verification, continue

        # Get signature headers
        timestamp = request.headers.get("x-slack-request-timestamp")
        signature = request.headers.get("x-slack-signature")

        # Skip verification if signing secret not configured (for development)
        if not settings.slack_signing_secret or settings.slack_signing_secret == "your_slack_signing_secret":
            logger.warning("Slack signing secret not configured - skipping verification")
            return await call_next(request)

        if not timestamp or not signature:
            logger.warning("Missing Slack signature headers")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Slack signature headers",
            )

        # Verify signature
        if not slack_service.verify_signature(body, timestamp, signature):
            logger.warning(
                "Invalid Slack request signature",
                path=request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature",
            )

        return await call_next(request)


async def verify_slack_signature(request: Request) -> bool:
    """Dependency for verifying Slack request signature.

    Args:
        request: FastAPI request

    Returns:
        True if valid
    """
    timestamp = request.headers.get("x-slack-request-timestamp")
    signature = request.headers.get("x-slack-signature")

    if not timestamp or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Slack signature headers",
        )

    body = await request.body()

    if not slack_service.verify_signature(body, timestamp, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid request signature",
        )

    return True
