"""User mapping repository for managing user identity mappings."""

from dataclasses import dataclass, field
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserMapping:
    """User identity mapping across platforms."""

    email: str
    zoom_user_id: str | None = None
    slack_user_id: str | None = None
    jira_account_id: str | None = None
    microsoft_user_id: str | None = None
    display_name: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class UserMappingRepository:
    """In-memory store for user mappings."""

    def __init__(self) -> None:
        """Initialize repository."""
        self._by_email: dict[str, UserMapping] = {}
        self._by_zoom_id: dict[str, str] = {}  # zoom_id -> email
        self._by_slack_id: dict[str, str] = {}  # slack_id -> email
        self._by_jira_id: dict[str, str] = {}  # jira_id -> email
        self._by_microsoft_id: dict[str, str] = {}  # microsoft_id -> email

    async def save(self, mapping: UserMapping) -> None:
        """Save or update user mapping."""
        existing = self._by_email.get(mapping.email)

        if existing:
            # Update existing
            if mapping.zoom_user_id:
                if existing.zoom_user_id:
                    del self._by_zoom_id[existing.zoom_user_id]
                existing.zoom_user_id = mapping.zoom_user_id
                self._by_zoom_id[mapping.zoom_user_id] = mapping.email

            if mapping.slack_user_id:
                if existing.slack_user_id:
                    del self._by_slack_id[existing.slack_user_id]
                existing.slack_user_id = mapping.slack_user_id
                self._by_slack_id[mapping.slack_user_id] = mapping.email

            if mapping.jira_account_id:
                if existing.jira_account_id:
                    del self._by_jira_id[existing.jira_account_id]
                existing.jira_account_id = mapping.jira_account_id
                self._by_jira_id[mapping.jira_account_id] = mapping.email

            if mapping.microsoft_user_id:
                if existing.microsoft_user_id:
                    del self._by_microsoft_id[existing.microsoft_user_id]
                existing.microsoft_user_id = mapping.microsoft_user_id
                self._by_microsoft_id[mapping.microsoft_user_id] = mapping.email

            if mapping.display_name:
                existing.display_name = mapping.display_name

            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            self._by_email[mapping.email] = mapping

            if mapping.zoom_user_id:
                self._by_zoom_id[mapping.zoom_user_id] = mapping.email

            if mapping.slack_user_id:
                self._by_slack_id[mapping.slack_user_id] = mapping.email

            if mapping.jira_account_id:
                self._by_jira_id[mapping.jira_account_id] = mapping.email

            if mapping.microsoft_user_id:
                self._by_microsoft_id[mapping.microsoft_user_id] = mapping.email

        logger.info(
            "Saved user mapping",
            email=mapping.email,
            has_zoom=bool(mapping.zoom_user_id),
            has_slack=bool(mapping.slack_user_id),
            has_jira=bool(mapping.jira_account_id),
            has_microsoft=bool(mapping.microsoft_user_id),
        )

    async def get_by_email(self, email: str) -> UserMapping | None:
        """Get user mapping by email."""
        return self._by_email.get(email.lower())

    async def get_by_zoom_id(self, zoom_user_id: str) -> UserMapping | None:
        """Get user mapping by Zoom user ID."""
        email = self._by_zoom_id.get(zoom_user_id)
        if email:
            return self._by_email.get(email)
        return None

    async def get_by_slack_id(self, slack_user_id: str) -> UserMapping | None:
        """Get user mapping by Slack user ID."""
        email = self._by_slack_id.get(slack_user_id)
        if email:
            return self._by_email.get(email)
        return None

    async def get_by_jira_id(self, jira_account_id: str) -> UserMapping | None:
        """Get user mapping by Jira account ID."""
        email = self._by_jira_id.get(jira_account_id)
        if email:
            return self._by_email.get(email)
        return None

    async def get_by_microsoft_id(self, microsoft_user_id: str) -> UserMapping | None:
        """Get user mapping by Microsoft user ID."""
        email = self._by_microsoft_id.get(microsoft_user_id)
        if email:
            return self._by_email.get(email)
        return None

    async def find_by_name(self, display_name: str) -> list[UserMapping]:
        """Find users by display name (partial match)."""
        name_lower = display_name.lower()
        return [
            mapping
            for mapping in self._by_email.values()
            if mapping.display_name and name_lower in mapping.display_name.lower()
        ]

    async def get_all(self) -> list[UserMapping]:
        """Get all user mappings."""
        return list(self._by_email.values())

    async def delete(self, email: str) -> bool:
        """Delete user mapping."""
        mapping = self._by_email.get(email)
        if not mapping:
            return False

        if mapping.zoom_user_id:
            del self._by_zoom_id[mapping.zoom_user_id]
        if mapping.slack_user_id:
            del self._by_slack_id[mapping.slack_user_id]
        if mapping.jira_account_id:
            del self._by_jira_id[mapping.jira_account_id]
        if mapping.microsoft_user_id:
            del self._by_microsoft_id[mapping.microsoft_user_id]

        del self._by_email[email]
        logger.info("Deleted user mapping", email=email)
        return True


# Singleton instance
user_mapping_repository = UserMappingRepository()
