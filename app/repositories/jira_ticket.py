"""Jira ticket repository for preventing duplicate ticket creation."""

import base64
from dataclasses import dataclass
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CreatedTicket:
    """Record of created Jira ticket."""

    meeting_id: str
    action_item_hash: str
    jira_key: str
    jira_id: str
    created_at: datetime


class JiraTicketRepository:
    """In-memory store for tracking created Jira tickets."""

    def __init__(self) -> None:
        """Initialize repository."""
        self._store: dict[str, CreatedTicket] = {}

    def _generate_key(self, meeting_id: str, task: str, owner_name: str) -> str:
        """Generate unique key for action item."""
        combined = f"{task}:{owner_name}"
        task_hash = base64.b64encode(combined.encode()).decode()[:32]
        return f"{meeting_id}:{task_hash}"

    async def exists(self, meeting_id: str, task: str, owner_name: str) -> bool:
        """Check if ticket already exists for action item."""
        key = self._generate_key(meeting_id, task, owner_name)
        return key in self._store

    async def save(
        self,
        meeting_id: str,
        task: str,
        owner_name: str,
        jira_key: str,
        jira_id: str,
    ) -> None:
        """Save created ticket reference."""
        key = self._generate_key(meeting_id, task, owner_name)

        self._store[key] = CreatedTicket(
            meeting_id=meeting_id,
            action_item_hash=key,
            jira_key=jira_key,
            jira_id=jira_id,
            created_at=datetime.utcnow(),
        )

        logger.info("Saved Jira ticket reference", meeting_id=meeting_id, jira_key=jira_key)

    async def get_by_meeting(self, meeting_id: str) -> list[CreatedTicket]:
        """Get all tickets for a meeting."""
        return [
            ticket
            for key, ticket in self._store.items()
            if key.startswith(f"{meeting_id}:")
        ]

    async def get(
        self, meeting_id: str, task: str, owner_name: str
    ) -> CreatedTicket | None:
        """Get specific ticket."""
        key = self._generate_key(meeting_id, task, owner_name)
        return self._store.get(key)


# Singleton instance
jira_ticket_repository = JiraTicketRepository()
