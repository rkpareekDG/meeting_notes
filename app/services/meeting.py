"""Meeting orchestration service - coordinates all meeting processing."""

import asyncio
from typing import Any

from app.config import settings
from app.models.types import MeetingSummary, ZoomWebhookPayload
from app.repositories import idempotency_repository
from app.services.jira import jira_service
from app.services.llm import llm_service
from app.services.outlook import outlook_service
from app.services.slack import slack_service
from app.services.zoom import zoom_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MeetingService:
    """Orchestrates meeting processing workflow."""

    def __init__(self) -> None:
        """Initialize meeting service."""
        pass

    async def process_recording_completed(
        self,
        payload: ZoomWebhookPayload,
    ) -> dict[str, Any]:
        """Process recording completed webhook.

        Args:
            payload: Zoom webhook payload

        Returns:
            Processing result
        """
        meeting_info = zoom_service.extract_meeting_info(payload)
        meeting_id = meeting_info["meeting_id"]

        logger.info(
            "Processing recording completed",
            meeting_id=meeting_id,
            topic=meeting_info["topic"],
        )

        # Check idempotency
        idempotency_key = f"recording:{meeting_id}"
        if await idempotency_repository.exists(idempotency_key):
            logger.info("Recording already processed", meeting_id=meeting_id)
            return {"status": "already_processed", "meeting_id": meeting_id}

        # Mark as processing
        await idempotency_repository.set(idempotency_key, "processing")

        try:
            # Find transcript in recording files
            transcript_url = None
            for file in meeting_info["recording_files"]:
                if file["file_type"] == "TRANSCRIPT" or file["recording_type"] == "audio_transcript":
                    transcript_url = file["download_url"]
                    break

            if not transcript_url:
                logger.warning("No transcript found", meeting_id=meeting_id)
                await idempotency_repository.set(idempotency_key, "no_transcript")
                return {"status": "no_transcript", "meeting_id": meeting_id}

            # Download and process transcript
            transcript = await zoom_service.download_transcript(meeting_id, transcript_url)

            # Generate AI summary
            summary = await llm_service.generate_meeting_summary(
                transcript,
                meeting_info["topic"],
            )

            # Send to Slack
            await self._send_summary_to_slack(meeting_id, meeting_info, summary)

            # Create Jira tickets if enabled
            if settings.jira_auto_create_tickets:
                await self._create_action_item_tickets(meeting_id, meeting_info, summary)

            # Notify action item owners
            await self._notify_action_owners(meeting_info, summary)

            # Mark as completed
            await idempotency_repository.set(idempotency_key, "completed")

            logger.info(
                "Successfully processed recording",
                meeting_id=meeting_id,
                action_items=len(summary.action_items),
            )

            return {
                "status": "success",
                "meeting_id": meeting_id,
                "action_items_count": len(summary.action_items),
            }

        except Exception as e:
            logger.error(
                "Failed to process recording",
                meeting_id=meeting_id,
                error=str(e),
            )
            await idempotency_repository.set(idempotency_key, f"error:{str(e)[:100]}")
            raise

    async def _send_summary_to_slack(
        self,
        meeting_id: str,
        meeting_info: dict[str, Any],
        summary: MeetingSummary,
    ) -> None:
        """Send meeting summary to Slack channel.

        Args:
            meeting_id: Meeting identifier
            meeting_info: Meeting metadata
            summary: Generated summary
        """
        channel = settings.slack_default_channel
        if not channel:
            logger.warning("No Slack channel configured")
            return

        try:
            await slack_service.send_meeting_summary(
                channel=channel,
                summary=summary,
                meeting_id=meeting_id,
                meeting_topic=meeting_info.get("topic"),
            )
            logger.info("Sent summary to Slack", channel=channel)
        except Exception as e:
            logger.error("Failed to send Slack summary", error=str(e))

    async def _create_action_item_tickets(
        self,
        meeting_id: str,
        meeting_info: dict[str, Any],
        summary: MeetingSummary,
    ) -> list[dict[str, Any]]:
        """Create Jira tickets for action items.

        Args:
            meeting_id: Meeting identifier
            meeting_info: Meeting metadata
            summary: Generated summary

        Returns:
            List of created tickets
        """
        if not summary.action_items:
            return []

        project_key = settings.jira_default_project
        if not project_key:
            logger.warning("No Jira project configured")
            return []

        created_tickets: list[dict[str, Any]] = []

        # Create tickets concurrently (with limit)
        tasks = []
        for action_item in summary.action_items:
            tasks.append(
                jira_service.create_ticket_from_action_item(
                    meeting_id=meeting_id,
                    action_item=action_item,
                    project_key=project_key,
                    meeting_topic=meeting_info.get("topic"),
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error("Failed to create ticket", error=str(result))
            elif result:
                created_tickets.append(result)

        logger.info(
            "Created Jira tickets",
            count=len(created_tickets),
            meeting_id=meeting_id,
        )

        return created_tickets

    async def _notify_action_owners(
        self,
        meeting_info: dict[str, Any],
        summary: MeetingSummary,
    ) -> None:
        """Notify action item owners via Slack DM.

        Args:
            meeting_info: Meeting metadata
            summary: Generated summary
        """
        for action_item in summary.action_items:
            if action_item.owner_email:
                try:
                    await slack_service.send_action_item_notification(
                        user_email=action_item.owner_email,
                        action_item=action_item,
                        meeting_topic=meeting_info.get("topic"),
                    )
                except Exception as e:
                    logger.error(
                        "Failed to notify action owner",
                        email=action_item.owner_email,
                        error=str(e),
                    )

    async def handle_create_jira_ticket_action(
        self,
        meeting_id: str,
        action_index: int,
        summary: MeetingSummary,
        meeting_topic: str | None = None,
    ) -> dict[str, Any] | None:
        """Handle Slack button action to create Jira ticket.

        Args:
            meeting_id: Meeting identifier
            action_index: Index of action item
            summary: Meeting summary
            meeting_topic: Optional meeting topic

        Returns:
            Created ticket or None
        """
        if action_index >= len(summary.action_items):
            logger.warning(
                "Invalid action index",
                meeting_id=meeting_id,
                index=action_index,
            )
            return None

        action_item = summary.action_items[action_index]
        project_key = settings.jira_default_project

        if not project_key:
            logger.warning("No Jira project configured")
            return None

        return await jira_service.create_ticket_from_action_item(
            meeting_id=meeting_id,
            action_item=action_item,
            project_key=project_key,
            meeting_topic=meeting_topic,
        )

    async def schedule_follow_up_meeting(
        self,
        meeting_id: str,
        meeting_info: dict[str, Any],
        summary: MeetingSummary,
    ) -> dict[str, Any] | None:
        """Schedule follow-up meeting based on action items.

        Args:
            meeting_id: Original meeting ID
            meeting_info: Meeting metadata
            summary: Generated summary

        Returns:
            Created event or None
        """
        from datetime import datetime, timedelta

        organizer_email = meeting_info.get("host_email")
        if not organizer_email:
            logger.warning("No organizer email found")
            return None

        # Collect attendee emails from action items
        attendee_emails = set()
        for item in summary.action_items:
            if item.owner_email:
                attendee_emails.add(item.owner_email)

        if not attendee_emails:
            logger.warning("No attendee emails found")
            return None

        # Schedule for 1 week from now
        start_time = datetime.utcnow() + timedelta(days=7)
        start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)

        # Build follow-up agenda
        follow_up_items = "\n".join(f"- {item.task}" for item in summary.action_items)
        body = f"""
<h2>Follow-up Meeting: {meeting_info.get('topic', 'Previous Meeting')}</h2>
<p>This is a follow-up meeting to review action items from our previous discussion.</p>
<h3>Action Items to Review:</h3>
<ul>
{follow_up_items}
</ul>
<h3>Follow-ups:</h3>
<ul>
{"".join(f"<li>{fu}</li>" for fu in summary.follow_ups)}
</ul>
        """.strip()

        try:
            event = await outlook_service.schedule_meeting(
                organizer_email=organizer_email,
                attendee_emails=list(attendee_emails),
                subject=f"Follow-up: {meeting_info.get('topic', 'Previous Meeting')}",
                body=body,
                start_time=start_time,
                duration_minutes=30,
            )

            logger.info(
                "Scheduled follow-up meeting",
                event_id=event.get("id"),
                meeting_id=meeting_id,
            )

            return event
        except Exception as e:
            logger.error("Failed to schedule follow-up", error=str(e))
            return None


# Singleton instance
meeting_service = MeetingService()
