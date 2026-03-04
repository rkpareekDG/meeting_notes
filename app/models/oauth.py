"""OAuth models for storing user tokens and authorization state."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    
    ZOOM = "zoom"
    MICROSOFT = "microsoft"
    JIRA = "jira"
    SLACK = "slack"


class OAuthToken(BaseModel):
    """OAuth token storage model."""
    
    user_id: str  # Slack user ID
    provider: OAuthProvider
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scope: str | None = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at


class OAuthState(BaseModel):
    """OAuth state for CSRF protection."""
    
    state: str
    user_id: str
    provider: OAuthProvider
    redirect_uri: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserAuthorization(BaseModel):
    """User's authorization status across providers."""
    
    user_id: str
    slack_user_name: str | None = None
    slack_team_id: str | None = None
    zoom_authorized: bool = False
    microsoft_authorized: bool = False
    jira_authorized: bool = False
    zoom_email: str | None = None
    microsoft_email: str | None = None
    jira_email: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
