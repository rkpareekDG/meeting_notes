"""Idempotency repository for preventing duplicate processing."""

from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar

from app.models.types import IdempotencyRecord, IdempotencyStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class IdempotencyRepository:
    """In-memory idempotency store with TTL support."""

    def __init__(self, default_ttl_hours: int = 24) -> None:
        """Initialize repository."""
        self._store: dict[str, IdempotencyRecord] = {}
        self._default_ttl = timedelta(hours=default_ttl_hours)

    async def acquire(self, key: str) -> bool:
        """
        Try to acquire an idempotency lock.

        Returns:
            True if lock acquired, False if already exists and not expired
        """
        existing = self._store.get(key)

        if existing:
            if existing.expires_at < datetime.utcnow():
                # Expired, remove and allow new acquisition
                del self._store[key]
            elif existing.status == IdempotencyStatus.COMPLETED:
                logger.info("Idempotency key already completed", key=key)
                return False
            elif existing.status == IdempotencyStatus.PROCESSING:
                logger.info("Idempotency key already processing", key=key)
                return False

        now = datetime.utcnow()
        record = IdempotencyRecord(
            key=key,
            status=IdempotencyStatus.PROCESSING,
            created_at=now,
            updated_at=now,
            expires_at=now + self._default_ttl,
        )

        self._store[key] = record
        logger.debug("Idempotency key acquired", key=key)
        return True

    async def complete(self, key: str, result: Any) -> None:
        """Mark idempotency key as completed with result."""
        record = self._store.get(key)
        if record:
            record.status = IdempotencyStatus.COMPLETED
            record.result = result
            record.updated_at = datetime.utcnow()
            self._store[key] = record
            logger.debug("Idempotency key completed", key=key)

    async def fail(self, key: str, error: str | None = None) -> None:
        """Mark idempotency key as failed."""
        record = self._store.get(key)
        if record:
            record.status = IdempotencyStatus.FAILED
            record.updated_at = datetime.utcnow()
            if error:
                record.result = {"error": error}
            self._store[key] = record
            logger.debug("Idempotency key failed", key=key, error=error)

    async def get(self, key: str) -> IdempotencyRecord | None:
        """Get idempotency record by key."""
        record = self._store.get(key)
        if not record:
            return None

        if record.expires_at < datetime.utcnow():
            del self._store[key]
            return None

        return record

    async def get_result(self, key: str) -> Any | None:
        """Get result from completed idempotency record."""
        record = await self.get(key)
        if record and record.status == IdempotencyStatus.COMPLETED:
            return record.result
        return None

    async def cleanup(self) -> int:
        """Remove expired records."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, record in self._store.items() if record.expires_at < now
        ]

        for key in expired_keys:
            del self._store[key]

        logger.info(f"Cleaned up {len(expired_keys)} expired idempotency records")
        return len(expired_keys)

    @staticmethod
    def generate_key(prefix: str, *parts: str) -> str:
        """Generate idempotency key from parts."""
        return f"{prefix}:{':'.join(parts)}"


# Singleton instance
idempotency_repository = IdempotencyRepository()
