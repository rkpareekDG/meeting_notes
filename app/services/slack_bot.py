"""Slack bot service for handling bot interactions and commands."""

import uuid
from typing import Any

import httpx

from app.config import settings
from app.models.oauth import OAuthProvider
from app.models.types import ProcessedTranscript
from app.repositories.oauth import oauth_repository
from app.services.oauth import oauth_service
from app.services.llm import llm_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SlackBotService:
    """Service for Slack bot interactions."""

    def __init__(self) -> None:
        """Initialize Slack bot service."""
        self._base_url = "https://slack.com/api"

    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Send message to Slack channel.
        
        Args:
            channel: Channel ID
            text: Message text (fallback)
            blocks: Block Kit blocks
            thread_ts: Thread timestamp for replies
            
        Returns:
            Slack API response
        """
        # Check if Slack token is configured
        if not settings.slack_bot_token:
            logger.warning("Slack bot token not configured, skipping message")
            return {"ok": False, "error": "not_configured"}
        
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
            return response.json()

    async def send_ephemeral(
        self,
        channel: str,
        user: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send ephemeral message (only visible to one user).
        
        Args:
            channel: Channel ID
            user: User ID
            text: Message text
            blocks: Block Kit blocks
            
        Returns:
            Slack API response
        """
        # Check if Slack token is configured
        if not settings.slack_bot_token:
            logger.warning("Slack bot token not configured, skipping ephemeral message")
            return {"ok": False, "error": "not_configured"}
        
        payload: dict[str, Any] = {
            "channel": channel,
            "user": user,
            "text": text,
        }
        
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/chat.postEphemeral",
                headers={
                    "Authorization": f"Bearer {settings.slack_bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            return response.json()

    async def handle_app_mention(
        self,
        user_id: str,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> None:
        """Handle when user mentions the bot.
        
        Args:
            user_id: Slack user ID
            channel: Channel ID
            text: Message text
            thread_ts: Thread timestamp
            files: Attached files (transcripts)
        """
        logger.info("Bot mentioned", user_id=user_id, channel=channel, has_files=bool(files))
        
        # Check if user uploaded a file (transcript)
        if files and len(files) > 0:
            await self._process_uploaded_transcript(user_id, channel, files[0], thread_ts)
            return
        
        # Get user's authorization status
        auth = await oauth_repository.get_authorization(user_id)
        
        # Check what command/intent
        text_lower = text.lower()
        
        if "setup" in text_lower or "connect" in text_lower or "authorize" in text_lower:
            await self._send_setup_message(user_id, channel, thread_ts)
        elif "status" in text_lower:
            await self._send_status_message(user_id, channel, auth, thread_ts)
        elif "help" in text_lower:
            await self._send_help_message(channel, thread_ts)
        elif "disconnect" in text_lower or "revoke" in text_lower:
            await self._send_disconnect_options(user_id, channel, auth, thread_ts)
        else:
            # Default welcome/help message
            await self._send_welcome_message(user_id, channel, auth, thread_ts)

    async def _send_welcome_message(
        self,
        user_id: str,
        channel: str,
        auth: Any,
        thread_ts: str | None = None,
    ) -> None:
        """Send welcome message with setup options."""
        # Check what's connected
        connected = []
        missing = []
        
        if auth.zoom_authorized:
            connected.append("✅ Zoom")
        else:
            missing.append("Zoom")
            
        if auth.microsoft_authorized:
            connected.append("✅ Microsoft 365")
        else:
            missing.append("Microsoft 365")
            
        if auth.jira_authorized:
            connected.append("✅ Jira")
        else:
            missing.append("Jira")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👋 Hi <@{user_id}>! I'm your AI Meeting Assistant.\n\n"
                            "I can help you:\n"
                            "• 📋 Summarize meeting recordings\n"
                            "• 🎯 Extract and track action items\n"
                            "• 📅 Schedule follow-up meetings\n"
                            "• 📝 Create Jira tickets automatically",
                },
            },
            {"type": "divider"},
        ]

        if connected:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Connected Services:*\n" + "\n".join(connected),
                },
            })

        if missing:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Connect your accounts to get started:*",
                },
            })
            
            buttons = []
            if "Zoom" in missing:
                buttons.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🎥 Connect Zoom", "emoji": True},
                    "url": oauth_service.get_zoom_auth_url(user_id),
                    "action_id": "connect_zoom",
                })
            if "Microsoft 365" in missing:
                buttons.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📅 Connect Outlook", "emoji": True},
                    "url": oauth_service.get_microsoft_auth_url(user_id),
                    "action_id": "connect_microsoft",
                })
            if "Jira" in missing:
                buttons.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📋 Connect Jira", "emoji": True},
                    "url": oauth_service.get_jira_auth_url(user_id),
                    "action_id": "connect_jira",
                })
            
            blocks.append({
                "type": "actions",
                "elements": buttons,
            })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 Try `@MeetingBot help` for more commands",
                }
            ],
        })

        await self.send_message(
            channel=channel,
            text="Hi! I'm your AI Meeting Assistant.",
            blocks=blocks,
            thread_ts=thread_ts,
        )

    async def _send_setup_message(
        self,
        user_id: str,
        channel: str,
        thread_ts: str | None = None,
    ) -> None:
        """Send setup/connect message with OAuth links."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🔗 *Connect Your Accounts*\n\n"
                            "Click the buttons below to authorize access to your accounts. "
                            "This allows me to process your meetings and create action items.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🎥 Zoom*\nAccess meeting recordings and transcripts",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Connect", "emoji": True},
                    "url": oauth_service.get_zoom_auth_url(user_id),
                    "style": "primary",
                    "action_id": "connect_zoom",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📅 Microsoft 365*\nSchedule follow-up meetings in Outlook",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Connect", "emoji": True},
                    "url": oauth_service.get_microsoft_auth_url(user_id),
                    "style": "primary",
                    "action_id": "connect_microsoft",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📋 Jira*\nCreate tickets for action items",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Connect", "emoji": True},
                    "url": oauth_service.get_jira_auth_url(user_id),
                    "style": "primary",
                    "action_id": "connect_jira",
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🔒 Your credentials are encrypted and stored securely. "
                                "You can disconnect anytime with `@MeetingBot disconnect`",
                    }
                ],
            },
        ]

        await self.send_ephemeral(
            channel=channel,
            user=user_id,
            text="Connect your accounts to get started",
            blocks=blocks,
        )

    async def _send_status_message(
        self,
        user_id: str,
        channel: str,
        auth: Any,
        thread_ts: str | None = None,
    ) -> None:
        """Send authorization status message."""
        status_lines = []
        
        if auth.zoom_authorized:
            status_lines.append(f"✅ *Zoom* - Connected as {auth.zoom_email or 'Unknown'}")
        else:
            status_lines.append("❌ *Zoom* - Not connected")
            
        if auth.microsoft_authorized:
            status_lines.append(f"✅ *Microsoft 365* - Connected as {auth.microsoft_email or 'Unknown'}")
        else:
            status_lines.append("❌ *Microsoft 365* - Not connected")
            
        if auth.jira_authorized:
            status_lines.append(f"✅ *Jira* - Connected as {auth.jira_email or 'Unknown'}")
        else:
            status_lines.append("❌ *Jira* - Not connected")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📊 *Your Connection Status*\n\n" + "\n".join(status_lines),
                },
            },
        ]

        # Add connect buttons for missing services
        missing_buttons = []
        if not auth.zoom_authorized:
            missing_buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Connect Zoom"},
                "url": oauth_service.get_zoom_auth_url(user_id),
                "action_id": "connect_zoom",
            })
        if not auth.microsoft_authorized:
            missing_buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Connect Outlook"},
                "url": oauth_service.get_microsoft_auth_url(user_id),
                "action_id": "connect_microsoft",
            })
        if not auth.jira_authorized:
            missing_buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Connect Jira"},
                "url": oauth_service.get_jira_auth_url(user_id),
                "action_id": "connect_jira",
            })

        if missing_buttons:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "actions",
                "elements": missing_buttons,
            })

        await self.send_ephemeral(
            channel=channel,
            user=user_id,
            text="Your connection status",
            blocks=blocks,
        )

    async def _send_help_message(
        self,
        channel: str,
        thread_ts: str | None = None,
    ) -> None:
        """Send help message."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📚 *AI Meeting Bot - Help*",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Commands:*\n\n"
                            "• `@MeetingBot setup` - Connect your Zoom, Outlook, and Jira accounts\n"
                            "• `@MeetingBot status` - Check your connection status\n"
                            "• `@MeetingBot disconnect` - Disconnect an account\n"
                            "• `@MeetingBot help` - Show this help message",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*How it works:*\n\n"
                            "1️⃣ Connect your accounts using `@MeetingBot setup`\n"
                            "2️⃣ Record a Zoom meeting with transcription enabled\n"
                            "3️⃣ I'll automatically process the recording when it's ready\n"
                            "4️⃣ You'll receive a summary with action items here in Slack\n"
                            "5️⃣ Click buttons to create Jira tickets or schedule follow-ups",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🤖 Powered by AI | 🔒 Your data is encrypted",
                    }
                ],
            },
        ]

        await self.send_message(
            channel=channel,
            text="AI Meeting Bot Help",
            blocks=blocks,
            thread_ts=thread_ts,
        )

    async def _send_disconnect_options(
        self,
        user_id: str,
        channel: str,
        auth: Any,
        thread_ts: str | None = None,
    ) -> None:
        """Send disconnect options."""
        connected = []
        
        if auth.zoom_authorized:
            connected.append(("zoom", "🎥 Zoom", auth.zoom_email))
        if auth.microsoft_authorized:
            connected.append(("microsoft", "📅 Microsoft 365", auth.microsoft_email))
        if auth.jira_authorized:
            connected.append(("jira", "📋 Jira", auth.jira_email))

        if not connected:
            await self.send_ephemeral(
                channel=channel,
                user=user_id,
                text="You don't have any connected accounts.",
            )
            return

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🔌 *Disconnect Accounts*\n\nSelect an account to disconnect:",
                },
            },
            {"type": "divider"},
        ]

        for provider, name, email in connected:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{name}*\nConnected as: {email or 'Unknown'}",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Disconnect"},
                    "style": "danger",
                    "value": f"{user_id}:{provider}",
                    "action_id": f"disconnect_{provider}",
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Disconnect Account"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Are you sure you want to disconnect {name}?",
                        },
                        "confirm": {"type": "plain_text", "text": "Disconnect"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
            })

        await self.send_ephemeral(
            channel=channel,
            user=user_id,
            text="Disconnect accounts",
            blocks=blocks,
        )

    async def handle_disconnect_action(
        self,
        user_id: str,
        provider: str,
        channel: str,
    ) -> None:
        """Handle disconnect button click.
        
        Args:
            user_id: Slack user ID
            provider: Provider to disconnect
            channel: Channel ID
        """
        try:
            oauth_provider = OAuthProvider(provider)
            deleted = await oauth_repository.delete_token(user_id, oauth_provider)
            
            if deleted:
                await self.send_ephemeral(
                    channel=channel,
                    user=user_id,
                    text=f"✅ Successfully disconnected {provider.title()}",
                )
            else:
                await self.send_ephemeral(
                    channel=channel,
                    user=user_id,
                    text=f"❌ {provider.title()} was not connected",
                )
        except Exception as e:
            logger.error("Failed to disconnect", error=str(e))
            await self.send_ephemeral(
                channel=channel,
                user=user_id,
                text=f"❌ Failed to disconnect: {str(e)}",
            )

    async def _process_uploaded_transcript(
        self,
        user_id: str,
        channel: str,
        file: dict[str, Any],
        thread_ts: str | None = None,
    ) -> None:
        """Process an uploaded transcript file.
        
        Args:
            user_id: Slack user ID
            channel: Channel ID
            file: Slack file object
            thread_ts: Thread timestamp
        """
        file_name = file.get("name", "transcript")
        file_type = file.get("filetype", "")
        file_id = file.get("id", "")
        file_url = file.get("url_private_download") or file.get("url_private", "")
        
        logger.info(
            "Processing uploaded transcript",
            user_id=user_id,
            file_name=file_name,
            file_type=file_type,
            file_id=file_id,
            file_url=file_url[:50] if file_url else "none",
        )
        
        # Send processing message
        await self.send_message(
            channel=channel,
            text=f"📄 Processing your transcript: *{file_name}*...",
            thread_ts=thread_ts,
        )
        
        try:
            # Download the file from Slack using proper authentication
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(
                    file_url,
                    headers={
                        "Authorization": f"Bearer {settings.slack_bot_token}",
                    },
                )
                
                logger.info(
                    "File download response",
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                )
                
                if response.status_code != 200:
                    # Try alternative: use files.info API
                    logger.warning("Direct download failed, trying files.info API")
                    file_info_response = await client.get(
                        f"{self._base_url}/files.info",
                        headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                        params={"file": file_id},
                    )
                    file_info = file_info_response.json()
                    
                    if file_info.get("ok") and file_info.get("file"):
                        alt_url = file_info["file"].get("url_private_download") or file_info["file"].get("url_private")
                        if alt_url:
                            response = await client.get(
                                alt_url,
                                headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                            )
                    
                    if response.status_code != 200:
                        await self.send_message(
                            channel=channel,
                            text=f"❌ Failed to download file: {response.status_code}. Please make sure the bot has `files:read` permission.",
                            thread_ts=thread_ts,
                        )
                        return
                
                transcript_content = response.text
            
            # Check if content is valid
            if not transcript_content or len(transcript_content.strip()) < 50:
                await self.send_message(
                    channel=channel,
                    text="❌ The file appears to be empty or too short. Please upload a valid transcript.",
                    thread_ts=thread_ts,
                )
                return
            
            # Extract meeting title from filename or use default
            meeting_title = file_name.replace(".txt", "").replace(".vtt", "").replace("_", " ")
            
            # Create ProcessedTranscript object from the raw text
            # Try to extract speakers from the transcript
            speakers = []
            lines = []
            for line in transcript_content.split("\n"):
                line = line.strip()
                if line and "]" in line:
                    # Format: [00:00:15] Speaker Name: text
                    try:
                        parts = line.split("]", 1)
                        if len(parts) > 1:
                            speaker_text = parts[1].strip()
                            if ":" in speaker_text:
                                speaker = speaker_text.split(":")[0].strip()
                                if speaker and speaker not in speakers:
                                    speakers.append(speaker)
                    except Exception:
                        pass
                if line:
                    lines.append({"text": line})
            
            processed_transcript = ProcessedTranscript(
                lines=lines,
                full_text=transcript_content,
                speakers=speakers,
            )
            
            # Generate AI summary
            await self.send_message(
                channel=channel,
                text="🤖 Analyzing transcript with AI...",
                thread_ts=thread_ts,
            )
            
            summary = await llm_service.generate_meeting_summary(
                processed_transcript,
                meeting_title,
            )
            
            # Format and send the summary
            await self._send_transcript_summary(
                channel=channel,
                meeting_title=meeting_title,
                summary=summary,
                user_id=user_id,
                thread_ts=thread_ts,
            )
            
            logger.info(
                "Successfully processed uploaded transcript",
                user_id=user_id,
                action_items=len(summary.action_items),
            )
            
        except Exception as e:
            logger.error("Failed to process transcript", error=str(e))
            await self.send_message(
                channel=channel,
                text=f"❌ Failed to process transcript: {str(e)}",
                thread_ts=thread_ts,
            )

    async def _send_transcript_summary(
        self,
        channel: str,
        meeting_title: str,
        summary: Any,
        user_id: str,
        thread_ts: str | None = None,
    ) -> None:
        """Send formatted transcript summary to Slack.
        
        Args:
            channel: Channel ID
            meeting_title: Meeting title
            summary: MeetingSummary object
            user_id: User ID who uploaded
            thread_ts: Thread timestamp
        """
        # Build action items text
        action_items_text = ""
        if summary.action_items:
            for i, item in enumerate(summary.action_items, 1):
                owner = item.owner_name or "Unassigned"
                due = f" (Due: {item.deadline})" if item.deadline else ""
                priority = f" [{item.priority}]" if item.priority else ""
                action_items_text += f"{i}. *{item.task}*{priority}\n   👤 {owner}{due}\n\n"
        else:
            action_items_text = "_No action items identified_"
        
        # Build key decisions text
        decisions_text = ""
        if summary.decisions:
            for decision in summary.decisions:
                decisions_text += f"• {decision}\n"
        else:
            decisions_text = "_No key decisions identified_"
        
        # Build key points text
        key_points_text = ""
        if summary.key_points:
            for point in summary.key_points[:5]:  # Limit to 5 points
                key_points_text += f"• {point}\n"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📋 Meeting Summary: {meeting_title[:50]}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📝 Summary*\n{summary.summary[:2000]}",  # Slack limit
                },
            },
            {"type": "divider"},
        ]
        
        # Add key points if available
        if key_points_text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📌 Key Points*\n{key_points_text}",
                },
            })
            blocks.append({"type": "divider"})
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🎯 Action Items*\n\n{action_items_text}",
            },
        })
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*💡 Key Decisions*\n{decisions_text}",
            },
        })
        blocks.append({"type": "divider"})
        
        # Add follow-ups if available
        if summary.follow_ups:
            follow_ups_text = "\n".join([f"• {fu}" for fu in summary.follow_ups[:5]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*� Follow-ups*\n{follow_ups_text}",
                },
            })
        
        # Add action buttons
        buttons = []
        
        # Check if user has Jira connected
        auth = await oauth_repository.get_authorization(user_id)
        if auth.jira_authorized and summary.action_items:
            buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "📋 Create Jira Tickets", "emoji": True},
                "style": "primary",
                "action_id": "create_jira_tickets",
                "value": f"transcript_{uuid.uuid4().hex[:8]}",
            })
        
        if auth.microsoft_authorized:
            buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "📅 Schedule Follow-up", "emoji": True},
                "action_id": "schedule_followup",
                "value": meeting_title,
            })
        
        if buttons:
            blocks.append({
                "type": "actions",
                "elements": buttons,
            })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🤖 Generated by AI Meeting Bot | Uploaded by <@{user_id}>",
                }
            ],
        })
        
        await self.send_message(
            channel=channel,
            text=f"Meeting Summary: {meeting_title}",
            blocks=blocks,
            thread_ts=thread_ts,
        )


# Singleton instance
slack_bot_service = SlackBotService()
