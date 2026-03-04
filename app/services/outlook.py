"""Microsoft Graph/Outlook service for calendar operations."""

from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import settings
from app.utils.encryption import encrypt, decrypt
from app.utils.logger import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)


class OutlookService:
    """Service for Microsoft Graph calendar operations."""

    def __init__(self) -> None:
        """Initialize Outlook service."""
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._graph_url = "https://graph.microsoft.com/v1.0"

    @async_retry(max_attempts=3)
    async def _get_access_token(self) -> str:
        """Get OAuth access token from Microsoft.

        Returns:
            Valid access token
        """
        if (
            self._access_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            return self._access_token

        logger.info("Fetching new Microsoft Graph access token")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data["access_token"]

            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)

            logger.info("Obtained Microsoft Graph access token", expires_in=expires_in)
            return self._access_token

    @async_retry(max_attempts=3)
    async def schedule_meeting(
        self,
        organizer_email: str,
        attendee_emails: list[str],
        subject: str,
        body: str,
        start_time: datetime,
        duration_minutes: int = 30,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Schedule a meeting via Microsoft Graph.

        Args:
            organizer_email: Organizer's email
            attendee_emails: List of attendee emails
            subject: Meeting subject
            body: Meeting body/description
            start_time: Meeting start time
            duration_minutes: Duration in minutes
            timezone: Timezone for the meeting

        Returns:
            Created event data
        """
        logger.info(
            "Scheduling meeting",
            organizer=organizer_email,
            attendees_count=len(attendee_emails),
        )

        token = await self._get_access_token()
        end_time = start_time + timedelta(minutes=duration_minutes)

        event_data = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body,
            },
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone,
            },
            "attendees": [
                {
                    "emailAddress": {"address": email},
                    "type": "required",
                }
                for email in attendee_emails
            ],
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._graph_url}/users/{organizer_email}/calendar/events",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=event_data,
            )
            response.raise_for_status()

            event = response.json()
            logger.info("Scheduled meeting", event_id=event.get("id"))
            return event

    @async_retry(max_attempts=2)
    async def get_availability(
        self,
        emails: list[str],
        start_time: datetime,
        end_time: datetime,
        timezone: str = "UTC",
    ) -> dict[str, list[dict[str, Any]]]:
        """Check availability for multiple users.

        Args:
            emails: List of email addresses
            start_time: Start of time range
            end_time: End of time range
            timezone: Timezone

        Returns:
            Availability data per user
        """
        logger.info("Checking availability", users_count=len(emails))

        token = await self._get_access_token()

        request_data = {
            "schedules": emails,
            "startTime": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone,
            },
            "endTime": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone,
            },
            "availabilityViewInterval": 30,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._graph_url}/me/calendar/getSchedule",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()

            data = response.json()
            schedules = data.get("value", [])

            result: dict[str, list[dict[str, Any]]] = {}
            for schedule in schedules:
                email = schedule.get("scheduleId", "")
                result[email] = schedule.get("scheduleItems", [])

            return result

    @async_retry(max_attempts=2)
    async def find_meeting_times(
        self,
        attendee_emails: list[str],
        duration_minutes: int = 30,
        time_constraint_start: datetime | None = None,
        time_constraint_end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Find available meeting times for attendees.

        Args:
            attendee_emails: List of attendee emails
            duration_minutes: Desired meeting duration
            time_constraint_start: Start of search window
            time_constraint_end: End of search window

        Returns:
            List of suggested meeting times
        """
        logger.info(
            "Finding meeting times",
            attendees_count=len(attendee_emails),
            duration=duration_minutes,
        )

        token = await self._get_access_token()

        now = datetime.utcnow()
        start = time_constraint_start or now
        end = time_constraint_end or (now + timedelta(days=7))

        request_data = {
            "attendees": [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendee_emails
            ],
            "timeConstraint": {
                "timeslots": [
                    {
                        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
                    }
                ]
            },
            "meetingDuration": f"PT{duration_minutes}M",
            "maxCandidates": 5,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._graph_url}/me/findMeetingTimes",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()

            data = response.json()
            suggestions = data.get("meetingTimeSuggestions", [])

            logger.info("Found meeting times", suggestions_count=len(suggestions))
            return suggestions

    @async_retry(max_attempts=2)
    async def get_calendar_events(
        self,
        user_email: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Get calendar events for a user.

        Args:
            user_email: User's email address
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of calendar events
        """
        logger.info("Fetching calendar events", user=user_email)

        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._graph_url}/users/{user_email}/calendarView",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "startDateTime": start_time.isoformat(),
                    "endDateTime": end_time.isoformat(),
                    "$select": "subject,start,end,attendees,isOnlineMeeting",
                    "$orderby": "start/dateTime",
                },
            )
            response.raise_for_status()

            data = response.json()
            events = data.get("value", [])

            logger.info("Fetched calendar events", count=len(events))
            return events

    async def store_user_token(self, user_email: str, token: str) -> None:
        """Store encrypted user token.

        Args:
            user_email: User's email
            token: OAuth token to store
        """
        encrypted = encrypt(token)
        # In production, store in database
        logger.info("Stored user token", user=user_email, encrypted_length=len(encrypted))

    async def get_user_token(self, user_email: str) -> str | None:
        """Retrieve decrypted user token.

        Args:
            user_email: User's email

        Returns:
            Decrypted token or None
        """
        # In production, retrieve from database
        encrypted_token = None  # Placeholder
        if encrypted_token:
            return decrypt(encrypted_token)
        return None


# Singleton instance
outlook_service = OutlookService()
