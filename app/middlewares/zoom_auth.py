"""Zoom webhook authentication middleware."""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.services.zoom import zoom_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ZoomAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for verifying Zoom webhook signatures."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and verify Zoom signature for webhook routes.

        Args:
            request: Incoming request
            call_next: Next handler

        Returns:
            Response
        """
        # Only apply to Zoom webhook routes
        if not request.url.path.startswith("/api/webhooks/zoom"):
            return await call_next(request)

        # Get signature headers
        timestamp = request.headers.get("x-zm-request-timestamp")
        signature = request.headers.get("x-zm-signature")

        if not timestamp or not signature:
            logger.warning("Missing Zoom signature headers")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Zoom signature headers",
            )

        # Read body
        body = await request.body()

        # Verify signature
        if not zoom_service.verify_webhook_signature(body, timestamp, signature):
            logger.warning(
                "Invalid Zoom webhook signature",
                path=request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

        return await call_next(request)


async def verify_zoom_signature(request: Request) -> bool:
    """Dependency for verifying Zoom webhook signature.

    Args:
        request: FastAPI request

    Returns:
        True if valid
    """
    timestamp = request.headers.get("x-zm-request-timestamp")
    signature = request.headers.get("x-zm-signature")

    if not timestamp or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Zoom signature headers",
        )

    body = await request.body()

    if not zoom_service.verify_webhook_signature(body, timestamp, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    return True
