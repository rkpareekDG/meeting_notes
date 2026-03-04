"""Logging utility with structured logging and sensitive data redaction."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config import settings


# Sensitive keys to redact from logs
SENSITIVE_KEYS = frozenset({
    "token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization",
    "bearer",
    "credential",
    "access_token",
    "refresh_token",
    "client_secret",
})


def sanitize_log_data(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize sensitive data from log entries."""
    sanitized = {}
    for key, value in data.items():
        lower_key = key.lower()
        is_sensitive = any(sk in lower_key for sk in SENSITIVE_KEYS)

        if is_sensitive:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        else:
            sanitized[key] = value

    return sanitized


def sanitize_processor(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor to sanitize sensitive data."""
    return sanitize_log_data(event_dict)


def configure_logging() -> None:
    """Configure structured logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Processors for structlog
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        sanitize_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance with context."""
    return structlog.get_logger(name)


# Configure on module load
configure_logging()
