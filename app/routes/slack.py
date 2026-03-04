"""Slack interaction routes."""

import json
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.middlewares import verify_slack_signature
from app.services import meeting_service, slack_service, jira_service
from app.services.slack_bot import slack_bot_service
from app.repositories import storage_repository
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/slack", tags=["slack"])


class SlackCommand(BaseModel):
    """Slack slash command payload."""

    command: str
    text: str | None = None
    response_url: str | None = None
    trigger_id: str | None = None
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str | None = None


@router.post("/events", response_model=None)
async def handle_slack_events(request: Request) -> JSONResponse:
    """Handle Slack events (Event Subscriptions API).

    Args:
        request: FastAPI request

    Returns:
        Response
    """
    body = await request.json()

    # Handle URL verification - MUST return challenge immediately
    if body.get("type") == "url_verification":
        challenge = body.get("challenge")
        logger.info("Responding to Slack URL verification challenge")
        # Return plain text challenge response for Slack verification
        return JSONResponse(
            content={"challenge": challenge},
            media_type="application/json"
        )

    # Handle events
    event_type = body.get("event", {}).get("type")
    logger.info("Received Slack event", event_type=event_type)

    # Handle app_mention event
    if event_type == "app_mention":
        await _handle_app_mention(body.get("event", {}))

    # Handle message events
    if event_type == "message":
        await _handle_message(body.get("event", {}))

    return JSONResponse(content={"status": "ok"})


@router.post("/interactions", response_model=None)
async def handle_slack_interactions(request: Request) -> dict[str, Any] | Response:
    """Handle Slack interactive components.

    Args:
        request: FastAPI request

    Returns:
        Response
    """
    # Parse form data
    form_data = await request.body()
    parsed = parse_qs(form_data.decode())
    payload_str = parsed.get("payload", ["{}"])[0]
    payload = json.loads(payload_str)

    interaction_type = payload.get("type")
    logger.info("Received Slack interaction", type=interaction_type)

    # Handle block actions (button clicks)
    if interaction_type == "block_actions":
        return await _handle_block_actions(payload)

    # Handle view submissions (modal forms)
    if interaction_type == "view_submission":
        return await _handle_view_submission(payload)

    return {"status": "ok"}


@router.post("/commands")
async def handle_slack_commands(request: Request) -> dict[str, Any]:
    """Handle Slack slash commands.

    Args:
        request: FastAPI request

    Returns:
        Response
    """
    form_data = await request.form()
    command = form_data.get("command", "")
    text = form_data.get("text", "")
    user_id = form_data.get("user_id", "")
    channel_id = form_data.get("channel_id", "")

    logger.info("Received Slack command", command=command, text=text)

    # Handle /meeting-summary command
    if command == "/meeting-summary":
        return await _handle_meeting_summary_command(text, user_id, channel_id)

    # Handle /create-ticket command
    if command == "/create-ticket":
        return await _handle_create_ticket_command(text, user_id, channel_id)

    return {
        "response_type": "ephemeral",
        "text": f"Unknown command: {command}",
    }


async def _handle_app_mention(event: dict[str, Any]) -> None:
    """Handle app mention events.

    Args:
        event: Slack event data
    """
    channel = event.get("channel")
    text = event.get("text", "")
    user = event.get("user")
    thread_ts = event.get("thread_ts")
    files = event.get("files", [])  # Get attached files

    logger.info("App mentioned", channel=channel, user=user, has_files=bool(files))

    # Use the slack bot service to handle mentions with OAuth flow
    if channel and user:
        await slack_bot_service.handle_app_mention(
            user_id=user,
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            files=files,  # Pass files to handler
        )


async def _handle_message(event: dict[str, Any]) -> None:
    """Handle direct message events.

    Args:
        event: Slack event data
    """
    # Ignore bot messages
    if event.get("bot_id"):
        return

    channel_type = event.get("channel_type")
    if channel_type != "im":
        return

    channel = event.get("channel")
    text = event.get("text", "").lower()

    logger.info("Received DM", channel=channel)

    # Simple help response
    if "help" in text:
        await slack_service.send_message(
            channel=channel,
            text="""*AI Meeting Bot Help*

I process Zoom meeting recordings and help with:
• 📋 Generating meeting summaries
• 🎯 Extracting action items
• 📝 Creating Jira tickets
• 📅 Scheduling follow-up meetings

Your meetings are processed automatically when recordings complete!""",
        )


async def _handle_block_actions(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle button clicks and other block actions.

    Args:
        payload: Slack interaction payload

    Returns:
        Response
    """
    actions = payload.get("actions", [])
    user = payload.get("user", {})
    channel = payload.get("channel", {})

    for action in actions:
        action_id = action.get("action_id", "")
        value = action.get("value", "")

        logger.info(
            "Processing block action",
            action_id=action_id,
            user=user.get("id"),
        )

        # Handle create Jira ticket button
        if action_id.startswith("create_jira_ticket_"):
            parts = value.split(":")
            if len(parts) == 2:
                meeting_id, action_index = parts[0], int(parts[1])
                # Would need to retrieve summary from storage
                await slack_service.send_message(
                    channel=channel.get("id"),
                    text=f"🎫 Creating Jira ticket for action item {action_index + 1}...",
                )

        # Handle create all tickets
        if action_id == "create_all_tickets":
            meeting_id = value
            await slack_service.send_message(
                channel=channel.get("id"),
                text="📝 Creating Jira tickets for all action items...",
            )

        # Handle schedule followup
        if action_id == "schedule_followup":
            meeting_id = value
            await slack_service.send_message(
                channel=channel.get("id"),
                text="📅 Opening follow-up scheduling...",
            )

        # Handle acknowledge
        if action_id == "acknowledge_action_item":
            await slack_service.send_message(
                channel=channel.get("id"),
                text="✅ Action item acknowledged!",
            )

        # Handle disconnect actions
        if action_id.startswith("disconnect_"):
            provider = action_id.replace("disconnect_", "")
            user_id = value.split(":")[0] if ":" in value else user.get("id")
            await slack_bot_service.handle_disconnect_action(
                user_id=user_id,
                provider=provider,
                channel=channel.get("id"),
            )

    return {"status": "ok"}


async def _handle_view_submission(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle modal form submissions.

    Args:
        payload: Slack interaction payload

    Returns:
        Response
    """
    view = payload.get("view", {})
    callback_id = view.get("callback_id")

    logger.info("Processing view submission", callback_id=callback_id)

    # Handle different modal submissions
    if callback_id == "schedule_followup_modal":
        # Process follow-up scheduling
        pass

    return {"response_action": "clear"}


async def _handle_meeting_summary_command(
    text: str,
    user_id: str,
    channel_id: str,
) -> dict[str, Any]:
    """Handle /meeting-summary command.

    Args:
        text: Command text (meeting ID)
        user_id: User who invoked command
        channel_id: Channel where command was invoked

    Returns:
        Response
    """
    if not text:
        return {
            "response_type": "ephemeral",
            "text": "Please provide a meeting ID: `/meeting-summary <meeting-id>`",
        }

    meeting_id = text.strip()

    # Check if we have stored data for this meeting
    transcript = await storage_repository.get_transcript(meeting_id)
    if not transcript:
        return {
            "response_type": "ephemeral",
            "text": f"No meeting found with ID: {meeting_id}",
        }

    return {
        "response_type": "in_channel",
        "text": f"📋 Fetching summary for meeting {meeting_id}...",
    }


async def _handle_create_ticket_command(
    text: str,
    user_id: str,
    channel_id: str,
) -> dict[str, Any]:
    """Handle /create-ticket command.

    Args:
        text: Command text (task description)
        user_id: User who invoked command
        channel_id: Channel where command was invoked

    Returns:
        Response
    """
    if not text:
        return {
            "response_type": "ephemeral",
            "text": "Please provide a task description: `/create-ticket <task description>`",
        }

    return {
        "response_type": "ephemeral",
        "text": f"🎫 Creating Jira ticket: {text}...",
    }
