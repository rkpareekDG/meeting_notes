"""Zoom API service for transcript downloads and meeting management."""

import hashlib
import hmac
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.models.types import ProcessedTranscript, ZoomWebhookPayload
from app.repositories import storage_repository
from app.utils.logger import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)


class ZoomService:
    """Service for interacting with Zoom API."""

    def __init__(self) -> None:
        """Initialize Zoom service."""
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    def verify_webhook_signature(
        self,
        payload: bytes,
        timestamp: str,
        signature: str,
    ) -> bool:
        """Verify Zoom webhook signature.

        Args:
            payload: Raw request body
            timestamp: Zoom timestamp header
            signature: Zoom signature header

        Returns:
            True if signature is valid
        """
        message = f"v0:{timestamp}:{payload.decode()}"
        expected = hmac.new(
            settings.zoom_webhook_secret_token.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        expected_signature = f"v0={expected}"
        return hmac.compare_digest(expected_signature, signature)

    def generate_challenge_response(self, plain_token: str) -> dict[str, str]:
        """Generate response for Zoom webhook validation.

        Args:
            plain_token: Plain token from Zoom challenge

        Returns:
            Challenge response with encrypted token
        """
        encrypted = hmac.new(
            settings.zoom_webhook_secret_token.encode(),
            plain_token.encode(),
            hashlib.sha256,
        ).hexdigest()

        return {
            "plainToken": plain_token,
            "encryptedToken": encrypted,
        }

    @async_retry(max_attempts=3)
    async def _get_access_token(self) -> str:
        """Get OAuth access token from Zoom.

        Returns:
            Valid access token
        """
        # Check if we have a valid cached token
        if (
            self._access_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            return self._access_token

        logger.info("Fetching new Zoom access token")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://zoom.us/oauth/token",
                params={"grant_type": "account_credentials", "account_id": settings.zoom_account_id},
                auth=(settings.zoom_client_id, settings.zoom_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data["access_token"]

            # Set expiry with 5 minute buffer
            expires_in = data.get("expires_in", 3600)
            from datetime import timedelta

            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)

            logger.info("Obtained Zoom access token", expires_in=expires_in)
            return self._access_token

    @async_retry(max_attempts=3)
    async def download_transcript(
        self,
        meeting_id: str,
        download_url: str,
    ) -> ProcessedTranscript:
        """Download and process meeting transcript.

        Args:
            meeting_id: Zoom meeting ID
            download_url: URL to download transcript from

        Returns:
            Processed transcript data
        """
        logger.info("Downloading transcript", meeting_id=meeting_id)

        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            # Download VTT file
            response = await client.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
            )
            response.raise_for_status()

            vtt_content = response.text

        # Parse VTT content
        transcript = self._parse_vtt(vtt_content)

        # Store transcript
        await storage_repository.save_transcript(meeting_id, transcript.full_text)

        logger.info(
            "Downloaded and processed transcript",
            meeting_id=meeting_id,
            line_count=len(transcript.lines),
        )

        return transcript

    def _parse_vtt(self, vtt_content: str) -> ProcessedTranscript:
        """Parse VTT content into structured transcript.

        Args:
            vtt_content: Raw VTT file content

        Returns:
            Processed transcript
        """
        lines: list[dict[str, Any]] = []
        full_text_parts: list[str] = []

        # Simple VTT parser
        current_speaker: str | None = None
        current_text: str | None = None

        for line in vtt_content.split("\n"):
            line = line.strip()

            # Skip headers and timestamps
            if (
                not line
                or line.startswith("WEBVTT")
                or line.startswith("NOTE")
                or "-->" in line
                or line.isdigit()
            ):
                continue

            # Check for speaker label (e.g., "John Doe: Hello")
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2 and len(parts[0]) < 50:  # Likely a speaker name
                    current_speaker = parts[0].strip()
                    current_text = parts[1].strip()
                else:
                    current_text = line
            else:
                current_text = line

            if current_text:
                lines.append({
                    "speaker": current_speaker or "Unknown",
                    "text": current_text,
                })
                full_text_parts.append(
                    f"{current_speaker or 'Unknown'}: {current_text}"
                )

        return ProcessedTranscript(
            lines=lines,
            full_text="\n".join(full_text_parts),
        )

    @async_retry(max_attempts=2)
    async def get_meeting_details(
        self,
        meeting_id: str,
    ) -> dict[str, Any]:
        """Get meeting details from Zoom.

        Args:
            meeting_id: Zoom meeting ID

        Returns:
            Meeting details
        """
        logger.info("Fetching meeting details", meeting_id=meeting_id)

        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.zoom.us/v2/meetings/{meeting_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()

            return response.json()

    @async_retry(max_attempts=2)
    async def get_meeting_participants(
        self,
        meeting_id: str,
    ) -> list[dict[str, Any]]:
        """Get meeting participants.

        Args:
            meeting_id: Zoom meeting ID

        Returns:
            List of participants
        """
        logger.info("Fetching meeting participants", meeting_id=meeting_id)

        token = await self._get_access_token()
        participants: list[dict[str, Any]] = []
        next_page_token: str | None = None

        async with httpx.AsyncClient() as client:
            while True:
                params: dict[str, Any] = {"page_size": 100}
                if next_page_token:
                    params["next_page_token"] = next_page_token

                response = await client.get(
                    f"https://api.zoom.us/v2/past_meetings/{meeting_id}/participants",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                response.raise_for_status()

                data = response.json()
                participants.extend(data.get("participants", []))

                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

        logger.info(
            "Fetched meeting participants",
            meeting_id=meeting_id,
            count=len(participants),
        )
        return participants

    def extract_meeting_info(
        self,
        payload: ZoomWebhookPayload,
    ) -> dict[str, Any]:
        """Extract relevant meeting info from webhook payload.

        Args:
            payload: Zoom webhook payload

        Returns:
            Extracted meeting information
        """
        obj = payload.payload.object
        return {
            "meeting_id": obj.uuid or obj.id,
            "topic": obj.topic,
            "host_id": obj.host_id,
            "host_email": obj.host_email,
            "duration": obj.duration,
            "start_time": obj.start_time,
            "recording_files": [
                {
                    "id": f.id,
                    "file_type": f.file_type,
                    "download_url": f.download_url,
                    "recording_type": f.recording_type,
                }
                for f in (obj.recording_files or [])
            ],
        }


# Singleton instance
zoom_service = ZoomService()
