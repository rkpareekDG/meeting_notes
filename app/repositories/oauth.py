"""OAuth token repository for storing and managing user OAuth tokens."""

from datetime import datetime
from typing import Any

from app.models.oauth import OAuthProvider, OAuthState, OAuthToken, UserAuthorization
from app.utils.encryption import encrypt, decrypt
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OAuthRepository:
    """In-memory OAuth token storage (use Redis/DB in production)."""

    def __init__(self) -> None:
        """Initialize repository."""
        # user_id -> provider -> token
        self._tokens: dict[str, dict[str, OAuthToken]] = {}
        # state -> OAuthState
        self._states: dict[str, OAuthState] = {}
        # user_id -> UserAuthorization
        self._authorizations: dict[str, UserAuthorization] = {}

    # Token management
    async def save_token(self, token: OAuthToken) -> None:
        """Save OAuth token for user.
        
        Args:
            token: OAuth token to save
        """
        if token.user_id not in self._tokens:
            self._tokens[token.user_id] = {}
        
        # Encrypt tokens before storing
        encrypted_token = OAuthToken(
            user_id=token.user_id,
            provider=token.provider,
            access_token=encrypt(token.access_token),
            refresh_token=encrypt(token.refresh_token) if token.refresh_token else None,
            token_type=token.token_type,
            expires_at=token.expires_at,
            scope=token.scope,
            extra_data=token.extra_data,
            created_at=token.created_at,
            updated_at=datetime.utcnow(),
        )
        
        self._tokens[token.user_id][token.provider.value] = encrypted_token
        
        # Update authorization status
        await self._update_authorization_status(token.user_id, token.provider, True)
        
        logger.info(
            "Saved OAuth token",
            user_id=token.user_id,
            provider=token.provider.value,
        )

    async def get_token(
        self, user_id: str, provider: OAuthProvider
    ) -> OAuthToken | None:
        """Get OAuth token for user and provider.
        
        Args:
            user_id: Slack user ID
            provider: OAuth provider
            
        Returns:
            Decrypted OAuth token or None
        """
        user_tokens = self._tokens.get(user_id, {})
        encrypted_token = user_tokens.get(provider.value)
        
        if not encrypted_token:
            return None
        
        # Decrypt tokens before returning
        return OAuthToken(
            user_id=encrypted_token.user_id,
            provider=encrypted_token.provider,
            access_token=decrypt(encrypted_token.access_token),
            refresh_token=decrypt(encrypted_token.refresh_token) if encrypted_token.refresh_token else None,
            token_type=encrypted_token.token_type,
            expires_at=encrypted_token.expires_at,
            scope=encrypted_token.scope,
            extra_data=encrypted_token.extra_data,
            created_at=encrypted_token.created_at,
            updated_at=encrypted_token.updated_at,
        )

    async def delete_token(self, user_id: str, provider: OAuthProvider) -> bool:
        """Delete OAuth token for user and provider.
        
        Args:
            user_id: Slack user ID
            provider: OAuth provider
            
        Returns:
            True if deleted
        """
        user_tokens = self._tokens.get(user_id, {})
        if provider.value in user_tokens:
            del user_tokens[provider.value]
            await self._update_authorization_status(user_id, provider, False)
            logger.info("Deleted OAuth token", user_id=user_id, provider=provider.value)
            return True
        return False

    async def get_user_tokens(self, user_id: str) -> dict[str, OAuthToken]:
        """Get all tokens for a user.
        
        Args:
            user_id: Slack user ID
            
        Returns:
            Dict of provider -> decrypted token
        """
        result = {}
        for provider_str, encrypted_token in self._tokens.get(user_id, {}).items():
            result[provider_str] = OAuthToken(
                user_id=encrypted_token.user_id,
                provider=encrypted_token.provider,
                access_token=decrypt(encrypted_token.access_token),
                refresh_token=decrypt(encrypted_token.refresh_token) if encrypted_token.refresh_token else None,
                token_type=encrypted_token.token_type,
                expires_at=encrypted_token.expires_at,
                scope=encrypted_token.scope,
                extra_data=encrypted_token.extra_data,
                created_at=encrypted_token.created_at,
                updated_at=encrypted_token.updated_at,
            )
        return result

    # State management for OAuth flow
    async def save_state(self, state: OAuthState) -> None:
        """Save OAuth state for CSRF protection.
        
        Args:
            state: OAuth state to save
        """
        self._states[state.state] = state
        logger.info("Saved OAuth state", user_id=state.user_id, provider=state.provider.value)

    async def get_state(self, state: str) -> OAuthState | None:
        """Get and consume OAuth state.
        
        Args:
            state: State string
            
        Returns:
            OAuthState if found
        """
        return self._states.pop(state, None)

    async def validate_state(self, state: str) -> OAuthState | None:
        """Validate OAuth state without consuming it.
        
        Args:
            state: State string
            
        Returns:
            OAuthState if valid
        """
        oauth_state = self._states.get(state)
        if not oauth_state:
            return None
        
        # Check if state is expired (5 minutes)
        from datetime import timedelta
        if datetime.utcnow() - oauth_state.created_at > timedelta(minutes=5):
            del self._states[state]
            return None
        
        return oauth_state

    # Authorization status
    async def _update_authorization_status(
        self, user_id: str, provider: OAuthProvider, authorized: bool
    ) -> None:
        """Update user's authorization status for a provider."""
        if user_id not in self._authorizations:
            self._authorizations[user_id] = UserAuthorization(user_id=user_id)
        
        auth = self._authorizations[user_id]
        auth.updated_at = datetime.utcnow()
        
        if provider == OAuthProvider.ZOOM:
            auth.zoom_authorized = authorized
        elif provider == OAuthProvider.MICROSOFT:
            auth.microsoft_authorized = authorized
        elif provider == OAuthProvider.JIRA:
            auth.jira_authorized = authorized

    async def get_authorization(self, user_id: str) -> UserAuthorization:
        """Get user's authorization status.
        
        Args:
            user_id: Slack user ID
            
        Returns:
            UserAuthorization status
        """
        if user_id not in self._authorizations:
            self._authorizations[user_id] = UserAuthorization(user_id=user_id)
        return self._authorizations[user_id]

    async def update_authorization(
        self, user_id: str, **kwargs: Any
    ) -> UserAuthorization:
        """Update user authorization details.
        
        Args:
            user_id: Slack user ID
            **kwargs: Fields to update
            
        Returns:
            Updated authorization
        """
        auth = await self.get_authorization(user_id)
        for key, value in kwargs.items():
            if hasattr(auth, key):
                setattr(auth, key, value)
        auth.updated_at = datetime.utcnow()
        return auth


# Singleton instance
oauth_repository = OAuthRepository()
