"""LLM service for AI-powered meeting analysis."""

import json
from typing import Any

from app.config import settings
from app.models.types import ActionItem, MeetingSummary, ProcessedTranscript
from app.utils.logger import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)


class LLMService:
    """Service for LLM-powered meeting analysis."""

    def __init__(self) -> None:
        """Initialize LLM service."""
        self._provider = settings.llm_provider  # "openai" or "gemini"
        self._openai_client = None
        self._gemini_client = None
        
        if self._provider == "gemini" and settings.gemini_api_key:
            from google import genai
            self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
            logger.info("Using Google Gemini for LLM")
        else:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self._model = settings.openai_model
            logger.info("Using OpenAI for LLM", model=settings.openai_model)

    @async_retry(max_attempts=3)
    async def generate_meeting_summary(
        self,
        transcript: ProcessedTranscript,
        meeting_topic: str | None = None,
    ) -> MeetingSummary:
        """Generate comprehensive meeting summary.

        Args:
            transcript: Processed transcript data
            meeting_topic: Optional meeting topic

        Returns:
            Meeting summary with action items
        """
        logger.info("Generating meeting summary", topic=meeting_topic, provider=self._provider)

        prompt = f"""You are an expert meeting analyst. Analyze the provided meeting transcript and extract:
1. A concise executive summary (2-3 paragraphs)
2. Key discussion points (bullet points)
3. Decisions made during the meeting
4. Action items with assignees, deadlines, and priority levels
5. Follow-up items that need attention

Format your response as JSON with the following structure:
{{
    "summary": "Executive summary text",
    "key_points": ["point 1", "point 2", ...],
    "decisions": ["decision 1", "decision 2", ...],
    "action_items": [
        {{
            "task": "Task description",
            "owner_name": "Person Name",
            "owner_email": "email@example.com or null if unknown",
            "deadline": "ISO date string or null",
            "priority": "HIGH" | "MEDIUM" | "LOW",
            "context": "Additional context"
        }}
    ],
    "follow_ups": ["follow up 1", "follow up 2", ...]
}}

Meeting Topic: {meeting_topic or 'Not specified'}

Transcript:
{transcript.full_text}

Analyze this transcript and provide the structured JSON summary. Return ONLY valid JSON, no markdown."""

        if self._provider == "gemini" and self._gemini_client:
            # Use Google Gemini
            response = await self._generate_with_gemini(prompt)
        else:
            # Use OpenAI
            response = await self._generate_with_openai(prompt)

        # Parse JSON response
        try:
            # Clean up response - remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON", error=str(e), response=response[:500])
            # Return a basic summary
            data = {
                "summary": "Unable to parse meeting summary. Please try again.",
                "key_points": [],
                "decisions": [],
                "action_items": [],
                "follow_ups": []
            }

        # Parse action items
        action_items: list[ActionItem] = []
        for item in data.get("action_items", []):
            action_items.append(
                ActionItem(
                    task=item.get("task", ""),
                    owner_name=item.get("owner_name", "Unassigned"),
                    owner_email=item.get("owner_email"),
                    deadline=item.get("deadline"),
                    priority=item.get("priority", "MEDIUM"),
                    context=item.get("context"),
                )
            )

        summary = MeetingSummary(
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            decisions=data.get("decisions", []),
            action_items=action_items,
            follow_ups=data.get("follow_ups", []),
        )

        logger.info(
            "Generated meeting summary",
            action_items_count=len(action_items),
            key_points_count=len(summary.key_points),
        )

        return summary

    async def _generate_with_gemini(self, prompt: str) -> str:
        """Generate response using Google Gemini."""
        import asyncio
        
        # Use the new google-genai SDK with gemini-1.5-flash (more available)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._gemini_client.models.generate_content(
                model="gemini-1.5-flash-latest",
                contents=prompt,
            )
        )
        return response.text

    async def _generate_with_openai(self, prompt: str) -> str:
        """Generate response using OpenAI."""
        response = await self._openai_client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or "{}"

    @async_retry(max_attempts=2)
    async def generate_slack_message(
        self,
        summary: MeetingSummary,
        meeting_topic: str | None = None,
    ) -> str:
        """Generate formatted Slack message from summary.

        Args:
            summary: Meeting summary
            meeting_topic: Optional meeting topic

        Returns:
            Formatted Slack message
        """
        logger.info("Generating Slack message")

        system_prompt = """You are a professional meeting assistant. Format the provided meeting summary 
into a well-structured Slack message using Slack's mrkdwn format.

Use:
- *bold* for headers and emphasis
- • for bullet points
- `code` for technical terms
- Emojis sparingly but effectively (📋, ✅, 📌, 🎯, etc.)
- Keep it professional but readable
- Include sections: Summary, Key Points, Decisions, Action Items"""

        user_prompt = f"""Format this meeting summary for Slack:

Topic: {meeting_topic or 'Team Meeting'}

Summary: {summary.summary}

Key Points: {json.dumps(summary.key_points)}

Decisions: {json.dumps(summary.decisions)}

Action Items: {json.dumps([item.model_dump() for item in summary.action_items])}"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )

        return response.choices[0].message.content or ""

    @async_retry(max_attempts=2)
    async def generate_jira_ticket_content(
        self,
        action_item: ActionItem,
        meeting_context: str | None = None,
    ) -> dict[str, str]:
        """Generate Jira ticket content from action item.

        Args:
            action_item: Action item to create ticket for
            meeting_context: Optional meeting context

        Returns:
            Dict with title and description
        """
        logger.info("Generating Jira ticket content", task=action_item.task[:50])

        system_prompt = """You are a project manager creating Jira tickets. 
Generate a clear, actionable ticket from the provided action item.

Respond with JSON:
{
    "title": "Clear, concise ticket title (max 100 chars)",
    "description": "Detailed description in Jira wiki markup format with context, acceptance criteria, and any relevant details"
}"""

        user_prompt = f"""Create a Jira ticket for this action item:

Task: {action_item.task}
Owner: {action_item.owner_name}
Priority: {action_item.priority}
Deadline: {action_item.deadline or 'Not specified'}
Context: {action_item.context or 'From meeting discussion'}

Additional Meeting Context: {meeting_context or 'None'}"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    @async_retry(max_attempts=2)
    async def extract_participant_names(
        self,
        transcript: ProcessedTranscript,
    ) -> list[str]:
        """Extract participant names from transcript.

        Args:
            transcript: Processed transcript

        Returns:
            List of participant names
        """
        logger.info("Extracting participant names")

        # First, extract unique speakers from parsed transcript
        speakers = set()
        for line in transcript.lines:
            speaker = line.get("speaker")
            if speaker and speaker != "Unknown":
                speakers.add(speaker)

        if speakers:
            return list(speakers)

        # If no speakers found in structured data, use LLM
        system_prompt = """Extract all participant/speaker names from this meeting transcript.
Return a JSON array of unique names only: ["Name1", "Name2", ...]"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript.full_text[:4000]},  # Limit context
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "[]"
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            return data.get("names", [])
        except json.JSONDecodeError:
            return []

    @async_retry(max_attempts=2)
    async def analyze_sentiment(
        self,
        transcript: ProcessedTranscript,
    ) -> dict[str, Any]:
        """Analyze meeting sentiment and engagement.

        Args:
            transcript: Processed transcript

        Returns:
            Sentiment analysis results
        """
        logger.info("Analyzing meeting sentiment")

        system_prompt = """Analyze the sentiment and engagement of this meeting transcript.
Return JSON:
{
    "overall_sentiment": "positive" | "neutral" | "negative",
    "engagement_level": "high" | "medium" | "low",
    "key_emotions": ["emotion1", "emotion2"],
    "concerns_raised": ["concern1", "concern2"],
    "positive_highlights": ["highlight1", "highlight2"]
}"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript.full_text[:6000]},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.loads(content)


# Singleton instance
llm_service = LLMService()
