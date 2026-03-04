"""Zoom webhook routes."""

from typing import Any

from fastapi import APIRouter, Request, Response, Depends, BackgroundTasks
from pydantic import BaseModel

from app.middlewares import verify_zoom_signature
from app.models.types import ZoomWebhookPayload
from app.services import meeting_service, zoom_service, queue_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks/zoom", tags=["zoom"])


class ChallengeResponse(BaseModel):
    """Zoom webhook challenge response."""

    plainToken: str
    encryptedToken: str


@router.post("")
async def handle_zoom_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Handle Zoom webhook events.

    Args:
        request: FastAPI request
        background_tasks: Background tasks

    Returns:
        Response
    """
    body = await request.json()
    event = body.get("event")

    logger.info("Received Zoom webhook", event=event)

    # Handle endpoint validation
    if event == "endpoint.url_validation":
        plain_token = body.get("payload", {}).get("plainToken")
        if plain_token:
            response = zoom_service.generate_challenge_response(plain_token)
            logger.info("Responding to Zoom challenge")
            return response

    # Handle recording completed
    if event == "recording.completed":
        try:
            payload = ZoomWebhookPayload(**body)

            # Process in background
            async def process():
                await meeting_service.process_recording_completed(payload)

            background_tasks.add_task(process)

            return {"status": "accepted"}

        except Exception as e:
            logger.error("Failed to process recording webhook", error=str(e))
            return {"status": "error", "message": str(e)}

    # Handle recording transcript completed
    if event == "recording.transcript_completed":
        try:
            payload = ZoomWebhookPayload(**body)

            async def process():
                await meeting_service.process_recording_completed(payload)

            background_tasks.add_task(process)

            return {"status": "accepted"}

        except Exception as e:
            logger.error("Failed to process transcript webhook", error=str(e))
            return {"status": "error", "message": str(e)}

    # Log unknown events
    logger.info("Unhandled Zoom webhook event", event=event)
    return {"status": "ignored", "event": event}


@router.post("/verified", dependencies=[Depends(verify_zoom_signature)])
async def handle_verified_zoom_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Handle Zoom webhook events with signature verification.

    Args:
        request: FastAPI request
        background_tasks: Background tasks

    Returns:
        Response
    """
    return await handle_zoom_webhook(request, background_tasks)
