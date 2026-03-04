"""OAuth service for handling OAuth flows with Zoom, Microsoft, and Jira."""

import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.models.oauth import OAuthProvider, OAuthState, OAuthToken
from app.repositories.oauth import oauth_repository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OAuthService:
    """Service for managing OAuth flows."""

    def __init__(self) -> None:
        """Initialize OAuth service."""
        self._base_url = settings.app_base_url

    # =========================================================================
    # Authorization URL Generation
    # =========================================================================

    def get_zoom_auth_url(self, user_id: str, redirect_uri: str | None = None) -> str:
        """Generate Zoom OAuth authorization URL.
        
        Args:
            user_id: Slack user ID
            redirect_uri: Optional custom redirect URI
            
        Returns:
            Authorization URL
        """
        state = self._generate_state(user_id, OAuthProvider.ZOOM)
        redirect = redirect_uri or f"{self._base_url}/api/oauth/zoom/callback"
        
        params = {
            "response_type": "code",
            "client_id": settings.zoom_client_id,
            "redirect_uri": redirect,
            "state": state,
        }
        
        return f"https://zoom.us/oauth/authorize?{urlencode(params)}"

    def get_microsoft_auth_url(self, user_id: str, redirect_uri: str | None = None) -> str:
        """Generate Microsoft OAuth authorization URL.
        
        Args:
            user_id: Slack user ID
            redirect_uri: Optional custom redirect URI
            
        Returns:
            Authorization URL
        """
        state = self._generate_state(user_id, OAuthProvider.MICROSOFT)
        redirect = redirect_uri or f"{self._base_url}/api/oauth/microsoft/callback"
        
        scopes = [
            "openid",
            "profile",
            "email",
            "offline_access",
            "Calendars.ReadWrite",
            "User.Read",
        ]
        
        params = {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": redirect,
            "response_mode": "query",
            "scope": " ".join(scopes),
            "state": state,
        }
        
        return f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/authorize?{urlencode(params)}"

    def get_jira_auth_url(self, user_id: str, redirect_uri: str | None = None) -> str:
        """Generate Jira/Atlassian OAuth authorization URL.
        
        Args:
            user_id: Slack user ID
            redirect_uri: Optional custom redirect URI
            
        Returns:
            Authorization URL
        """
        state = self._generate_state(user_id, OAuthProvider.JIRA)
        redirect = redirect_uri or f"{self._base_url}/api/oauth/jira/callback"
        
        scopes = [
            "read:jira-work",
            "write:jira-work",
            "read:jira-user",
            "offline_access",
        ]
        
        params = {
            "audience": "api.atlassian.com",
            "client_id": settings.jira_oauth_client_id,
            "scope": " ".join(scopes),
            "redirect_uri": redirect,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        
        return f"https://auth.atlassian.com/authorize?{urlencode(params)}"

    def _generate_state(self, user_id: str, provider: OAuthProvider) -> str:
        """Generate and store OAuth state for CSRF protection."""
        import asyncio
        
        state = secrets.token_urlsafe(32)
        oauth_state = OAuthState(
            state=state,
            user_id=user_id,
            provider=provider,
        )
        
        # Save state (run sync in async context)
        asyncio.create_task(oauth_repository.save_state(oauth_state))
        
        return state

    # =========================================================================
    # Token Exchange
    # =========================================================================

    async def exchange_zoom_code(self, code: str, state: str) -> OAuthToken | None:
        """Exchange Zoom authorization code for tokens.
        
        Args:
            code: Authorization code
            state: State for CSRF validation
            
        Returns:
            OAuth token or None if failed
        """
        oauth_state = await oauth_repository.get_state(state)
        if not oauth_state or oauth_state.provider != OAuthProvider.ZOOM:
            logger.error("Invalid OAuth state for Zoom")
            return None

        redirect_uri = f"{self._base_url}/api/oauth/zoom/callback"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://zoom.us/oauth/token",
                params={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(settings.zoom_client_id, settings.zoom_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error("Failed to exchange Zoom code", status=response.status_code)
                return None
            
            data = response.json()
            
            # Get user info
            user_info = await self._get_zoom_user_info(data["access_token"])
            
            token = OAuthToken(
                user_id=oauth_state.user_id,
                provider=OAuthProvider.ZOOM,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
                extra_data={"zoom_user": user_info},
            )
            
            await oauth_repository.save_token(token)
            
            # Update authorization with email
            if user_info:
                await oauth_repository.update_authorization(
                    oauth_state.user_id,
                    zoom_email=user_info.get("email"),
                )
            
            logger.info("Exchanged Zoom code successfully", user_id=oauth_state.user_id)
            return token

    async def exchange_microsoft_code(self, code: str, state: str) -> OAuthToken | None:
        """Exchange Microsoft authorization code for tokens.
        
        Args:
            code: Authorization code
            state: State for CSRF validation
            
        Returns:
            OAuth token or None if failed
        """
        oauth_state = await oauth_repository.get_state(state)
        if not oauth_state or oauth_state.provider != OAuthProvider.MICROSOFT:
            logger.error("Invalid OAuth state for Microsoft")
            return None

        redirect_uri = f"{self._base_url}/api/oauth/microsoft/callback"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error("Failed to exchange Microsoft code", status=response.status_code)
                return None
            
            data = response.json()
            
            # Get user info
            user_info = await self._get_microsoft_user_info(data["access_token"])
            
            token = OAuthToken(
                user_id=oauth_state.user_id,
                provider=OAuthProvider.MICROSOFT,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
                extra_data={"microsoft_user": user_info},
            )
            
            await oauth_repository.save_token(token)
            
            # Update authorization with email
            if user_info:
                await oauth_repository.update_authorization(
                    oauth_state.user_id,
                    microsoft_email=user_info.get("mail") or user_info.get("userPrincipalName"),
                )
            
            logger.info("Exchanged Microsoft code successfully", user_id=oauth_state.user_id)
            return token

    async def exchange_jira_code(self, code: str, state: str) -> OAuthToken | None:
        """Exchange Jira/Atlassian authorization code for tokens.
        
        Args:
            code: Authorization code
            state: State for CSRF validation
            
        Returns:
            OAuth token or None if failed
        """
        oauth_state = await oauth_repository.get_state(state)
        if not oauth_state or oauth_state.provider != OAuthProvider.JIRA:
            logger.error("Invalid OAuth state for Jira")
            return None

        redirect_uri = f"{self._base_url}/api/oauth/jira/callback"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "client_id": settings.jira_oauth_client_id,
                    "client_secret": settings.jira_oauth_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code != 200:
                logger.error("Failed to exchange Jira code", status=response.status_code)
                return None
            
            data = response.json()
            
            # Get accessible resources (Jira sites)
            resources = await self._get_jira_resources(data["access_token"])
            
            # Get user info
            user_info = await self._get_jira_user_info(data["access_token"])
            
            token = OAuthToken(
                user_id=oauth_state.user_id,
                provider=OAuthProvider.JIRA,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
                extra_data={
                    "jira_user": user_info,
                    "jira_resources": resources,
                },
            )
            
            await oauth_repository.save_token(token)
            
            # Update authorization with email
            if user_info:
                await oauth_repository.update_authorization(
                    oauth_state.user_id,
                    jira_email=user_info.get("email"),
                )
            
            logger.info("Exchanged Jira code successfully", user_id=oauth_state.user_id)
            return token

    # =========================================================================
    # Token Refresh
    # =========================================================================

    async def refresh_token(self, user_id: str, provider: OAuthProvider) -> OAuthToken | None:
        """Refresh OAuth token for user.
        
        Args:
            user_id: Slack user ID
            provider: OAuth provider
            
        Returns:
            Refreshed token or None
        """
        token = await oauth_repository.get_token(user_id, provider)
        if not token or not token.refresh_token:
            return None

        if provider == OAuthProvider.ZOOM:
            return await self._refresh_zoom_token(token)
        elif provider == OAuthProvider.MICROSOFT:
            return await self._refresh_microsoft_token(token)
        elif provider == OAuthProvider.JIRA:
            return await self._refresh_jira_token(token)
        
        return None

    async def _refresh_zoom_token(self, token: OAuthToken) -> OAuthToken | None:
        """Refresh Zoom token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://zoom.us/oauth/token",
                params={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token,
                },
                auth=(settings.zoom_client_id, settings.zoom_client_secret),
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            new_token = OAuthToken(
                user_id=token.user_id,
                provider=OAuthProvider.ZOOM,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", token.refresh_token),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
                extra_data=token.extra_data,
            )
            
            await oauth_repository.save_token(new_token)
            return new_token

    async def _refresh_microsoft_token(self, token: OAuthToken) -> OAuthToken | None:
        """Refresh Microsoft token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "refresh_token": token.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            new_token = OAuthToken(
                user_id=token.user_id,
                provider=OAuthProvider.MICROSOFT,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", token.refresh_token),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
                extra_data=token.extra_data,
            )
            
            await oauth_repository.save_token(new_token)
            return new_token

    async def _refresh_jira_token(self, token: OAuthToken) -> OAuthToken | None:
        """Refresh Jira token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "client_id": settings.jira_oauth_client_id,
                    "client_secret": settings.jira_oauth_client_secret,
                    "refresh_token": token.refresh_token,
                },
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            new_token = OAuthToken(
                user_id=token.user_id,
                provider=OAuthProvider.JIRA,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", token.refresh_token),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
                extra_data=token.extra_data,
            )
            
            await oauth_repository.save_token(new_token)
            return new_token

    # =========================================================================
    # User Info Helpers
    # =========================================================================

    async def _get_zoom_user_info(self, access_token: str) -> dict[str, Any] | None:
        """Get Zoom user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.zoom.us/v2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
        return None

    async def _get_microsoft_user_info(self, access_token: str) -> dict[str, Any] | None:
        """Get Microsoft user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
        return None

    async def _get_jira_user_info(self, access_token: str) -> dict[str, Any] | None:
        """Get Jira/Atlassian user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.atlassian.com/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
        return None

    async def _get_jira_resources(self, access_token: str) -> list[dict[str, Any]]:
        """Get accessible Jira resources/sites."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
        return []

    # =========================================================================
    # Token Access for Services
    # =========================================================================

    async def get_valid_token(
        self, user_id: str, provider: OAuthProvider
    ) -> str | None:
        """Get a valid access token, refreshing if needed.
        
        Args:
            user_id: Slack user ID
            provider: OAuth provider
            
        Returns:
            Valid access token or None
        """
        token = await oauth_repository.get_token(user_id, provider)
        if not token:
            return None
        
        # Refresh if expired or about to expire (5 min buffer)
        if token.expires_at:
            buffer = timedelta(minutes=5)
            if datetime.utcnow() + buffer >= token.expires_at:
                token = await self.refresh_token(user_id, provider)
                if not token:
                    return None
        
        return token.access_token


# Singleton instance
oauth_service = OAuthService()
