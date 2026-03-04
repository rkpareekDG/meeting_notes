"""Slack service for sending messages and interactive notifications."""

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.config import settings
from app.models.types import ActionItem, MeetingSummary
from app.utils.logger import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)


class SlackService:
    """Service for Slack interactions."""

    def __init__(self) -> None:
        """Initialize Slack service."""
        self._base_url = "https://slack.com/api"

    def verify_signature(
        self,
        body: bytes,
        timestamp: str,
        signature: str,
    ) -> bool:
        """Verify Slack request signature.

        Args:
            body: Raw request body
            timestamp: Slack timestamp header
            signature: Slack signature header

        Returns:
            True if signature is valid
        """
        # Check timestamp to prevent replay attacks
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 60 * 5:
            return False

        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected_signature = (
            "v0="
            + hmac.new(
                settings.slack_signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(expected_signature, signature)

    @async_retry(max_attempts=3)
    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Send message to Slack channel.

        Args:
            channel: Channel ID or name
            text: Message text (fallback for notifications)
            blocks: Optional Block Kit blocks
            thread_ts: Optional thread timestamp for replies

        Returns:
            Slack API response
        """
        logger.info("Sending Slack message", channel=channel)

        payload: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }

        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {settings.slack_bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            if not data.get("ok"):
                logger.error("Slack API error", error=data.get("error"))
                raise Exception(f"Slack API error: {data.get('error')}")

            logger.info("Sent Slack message", ts=data.get("ts"))
            return data

    async def send_meeting_summary(
        self,
        channel: str,
        summary: MeetingSummary,
        meeting_id: str,
        meeting_topic: str | None = None,
    ) -> dict[str, Any]:
        """Send formatted meeting summary to Slack.

        Args:
            channel: Channel ID
            summary: Meeting summary
            meeting_id: Meeting identifier
            meeting_topic: Optional meeting topic

        Returns:
            Slack API response
        """
        blocks = self._build_summary_blocks(summary, meeting_id, meeting_topic)
        text = f"Meeting Summary: {meeting_topic or 'Team Meeting'}"

        return await self.send_message(channel, text, blocks)

    def _build_summary_blocks(
        self,
        summary: MeetingSummary,
        meeting_id: str,
        meeting_topic: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build Slack Block Kit blocks for meeting summary.

        Args:
            summary: Meeting summary
            meeting_id: Meeting identifier
            meeting_topic: Optional meeting topic

        Returns:
            List of Block Kit blocks
        """
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📋 Meeting Summary: {meeting_topic or 'Team Meeting'}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary*\n{summary.summary}",
                },
            },
        ]

        # Key points
        if summary.key_points:
            points_text = "\n".join(f"• {point}" for point in summary.key_points[:5])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📌 Key Points*\n{points_text}",
                },
            })

        # Decisions
        if summary.decisions:
            decisions_text = "\n".join(f"• {decision}" for decision in summary.decisions[:5])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*✅ Decisions Made*\n{decisions_text}",
                },
            })

        # Action items
        if summary.action_items:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🎯 Action Items*",
                },
            })

            for i, item in enumerate(summary.action_items[:10]):
                priority_emoji = {
                    "HIGH": "🔴",
                    "MEDIUM": "🟡",
                    "LOW": "🟢",
                }.get(item.priority, "⚪")

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"{priority_emoji} *{item.task}*\n"
                            f"👤 {item.owner_name}"
                            + (f" | 📅 {item.deadline}" if item.deadline else "")
                        ),
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Create Jira Ticket",
                            "emoji": True,
                        },
                        "value": f"{meeting_id}:{i}",
                        "action_id": f"create_jira_ticket_{i}",
                    },
                })

        # Follow-ups
        if summary.follow_ups:
            followups_text = "\n".join(f"• {fu}" for fu in summary.follow_ups[:5])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📎 Follow-ups*\n{followups_text}",
                },
            })

        # Footer with actions
        blocks.extend([
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📅 Schedule Follow-up",
                            "emoji": True,
                        },
                        "value": meeting_id,
                        "action_id": "schedule_followup",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📝 Create All Tickets",
                            "emoji": True,
                        },
                        "value": meeting_id,
                        "action_id": "create_all_tickets",
                        "style": "primary",
                    },
                ],
            },
        ])

        return blocks

    @async_retry(max_attempts=2)
    async def send_dm(
        self,
        user_id: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send direct message to user.

        Args:
            user_id: Slack user ID
            text: Message text
            blocks: Optional Block Kit blocks

        Returns:
            Slack API response
        """
        logger.info("Sending Slack DM", user_id=user_id)

        # Open DM channel
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/conversations.open",
                headers={
                    "Authorization": f"Bearer {settings.slack_bot_token}",
                    "Content-Type": "application/json",
                },
                json={"users": user_id},
            )
            response.raise_for_status()

            data = response.json()
            if not data.get("ok"):
                raise Exception(f"Failed to open DM: {data.get('error')}")

            channel = data["channel"]["id"]

        return await self.send_message(channel, text, blocks)

    @async_retry(max_attempts=2)
    async def lookup_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Look up Slack user by email.

        Args:
            email: User email address

        Returns:
            User info or None if not found
        """
        logger.info("Looking up Slack user", email=email)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/users.lookupByEmail",
                headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                params={"email": email},
            )
            response.raise_for_status()

            data = response.json()
            if data.get("ok"):
                return data.get("user")
            return None

    async def send_action_item_notification(
        self,
        user_email: str,
        action_item: ActionItem,
        meeting_topic: str | None = None,
    ) -> bool:
        """Send action item notification to user.

        Args:
            user_email: User's email
            action_item: Action item assigned
            meeting_topic: Optional meeting topic

        Returns:
            True if sent successfully
        """
        user = await self.lookup_user_by_email(user_email)
        if not user:
            logger.warning("User not found in Slack", email=user_email)
            return False

        priority_emoji = {
            "HIGH": "🔴",
            "MEDIUM": "🟡",
            "LOW": "🟢",
        }.get(action_item.priority, "⚪")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*You have a new action item from: {meeting_topic or 'a meeting'}*\n\n"
                        f"{priority_emoji} *Task:* {action_item.task}\n"
                        f"📅 *Deadline:* {action_item.deadline or 'Not specified'}"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Acknowledge",
                            "emoji": True,
                        },
                        "style": "primary",
                        "action_id": "acknowledge_action_item",
                    },
                ],
            },
        ]

        await self.send_dm(
            user["id"],
            f"New action item: {action_item.task}",
            blocks,
        )
        return True

    @async_retry(max_attempts=2)
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update existing Slack message.

        Args:
            channel: Channel ID
            ts: Message timestamp
            text: New message text
            blocks: Optional new blocks

        Returns:
            Slack API response
        """
        logger.info("Updating Slack message", channel=channel, ts=ts)

        payload: dict[str, Any] = {
            "channel": channel,
            "ts": ts,
            "text": text,
        }
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/chat.update",
                headers={
                    "Authorization": f"Bearer {settings.slack_bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            if not data.get("ok"):
                raise Exception(f"Failed to update message: {data.get('error')}")

            return data


# Singleton instance
slack_service = SlackService()
