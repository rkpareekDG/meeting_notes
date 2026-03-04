"""Configuration module with environment validation using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "production", "test"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=3000, alias="PORT")

    # Zoom (optional with defaults for development)
    zoom_webhook_secret_token: str = Field(
        default="your-webhook-secret", alias="ZOOM_WEBHOOK_SECRET_TOKEN"
    )
    zoom_client_id: str = Field(default="", alias="ZOOM_CLIENT_ID")
    zoom_client_secret: str = Field(default="", alias="ZOOM_CLIENT_SECRET")
    zoom_account_id: str = Field(default="", alias="ZOOM_ACCOUNT_ID")

    # Slack (optional with defaults for development)
    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    slack_signing_secret: str = Field(default="your-signing-secret", alias="SLACK_SIGNING_SECRET")
    slack_app_token: str = Field(default="", alias="SLACK_APP_TOKEN")
    slack_default_channel: str = Field(default="general", alias="SLACK_DEFAULT_CHANNEL")

    # LLM Provider (openai or gemini)
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    
    # OpenAI (optional with defaults for development)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4096, alias="OPENAI_MAX_TOKENS")
    
    # Google Gemini (free alternative)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Microsoft Graph (optional with defaults for development)
    microsoft_client_id: str = Field(default="", alias="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: str = Field(default="", alias="MICROSOFT_CLIENT_SECRET")
    microsoft_tenant_id: str = Field(default="", alias="MICROSOFT_TENANT_ID")

    # Jira (optional with defaults for development)
    jira_host: str = Field(default="", alias="JIRA_HOST")
    jira_email: str = Field(default="", alias="JIRA_EMAIL")
    jira_api_token: str = Field(default="", alias="JIRA_API_TOKEN")
    jira_default_project: str = Field(default="", alias="JIRA_DEFAULT_PROJECT")
    jira_auto_create_tickets: bool = Field(default=False, alias="JIRA_AUTO_CREATE_TICKETS")
    
    # Jira OAuth (for user-based auth)
    jira_oauth_client_id: str = Field(default="", alias="JIRA_OAUTH_CLIENT_ID")
    jira_oauth_client_secret: str = Field(default="", alias="JIRA_OAUTH_CLIENT_SECRET")

    # OAuth Settings
    oauth_redirect_base_url: str = Field(
        default="http://localhost:3000", alias="OAUTH_REDIRECT_BASE_URL"
    )
    
    # Zoom OAuth (user-based auth)
    zoom_oauth_redirect_uri: str = Field(
        default="", alias="ZOOM_OAUTH_REDIRECT_URI"
    )
    
    # Microsoft OAuth (user-based auth)
    microsoft_oauth_redirect_uri: str = Field(
        default="", alias="MICROSOFT_OAUTH_REDIRECT_URI"
    )
    
    # Jira OAuth redirect
    jira_oauth_redirect_uri: str = Field(
        default="", alias="JIRA_OAUTH_REDIRECT_URI"
    )

    # Storage
    storage_type: Literal["local", "s3"] = Field(default="local", alias="STORAGE_TYPE")
    storage_path: str = Field(default="./data/transcripts", alias="STORAGE_PATH")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Security
    encryption_key: str = Field(
        default="01234567890123456789012345678901",  # 32-byte default for dev
        alias="ENCRYPTION_KEY",
        min_length=32,
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        alias="CORS_ORIGINS",
    )

    @field_validator("storage_path")
    @classmethod
    def resolve_storage_path(cls, v: str) -> str:
        """Resolve storage path to absolute path."""
        return str(Path(v).resolve())

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "test"

    @property
    def app_base_url(self) -> str:
        """Get the application base URL for OAuth redirects."""
        return self.oauth_redirect_base_url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export singleton
settings = get_settings()
