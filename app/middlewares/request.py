"""Request logging and context middleware."""

import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.utils.logger import get_logger

logger = get_logger(__name__)


class RequestMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging and context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add request context and log requests.

        Args:
            request: Incoming request
            call_next: Next handler

        Returns:
            Response
        """
        # Generate request ID
        request_id = request.headers.get("x-request-id", str(uuid4()))
        
        # Store in request state
        request.state.request_id = request_id
        
        # Log incoming request
        start_time = time.time()
        
        logger.info(
            "Incoming request",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
            client_ip=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                request_id=request_id,
            )
            
            # Add request ID to response headers
            response.headers["x-request-id"] = request_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
                request_id=request_id,
            )
            raise
