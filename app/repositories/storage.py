"""Storage repository for transcript storage."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import aiofiles

from app.config import settings
from app.models.types import StoredTranscript
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IStorageRepository(Protocol):
    """Storage repository interface."""

    async def save(
        self, key: str, content: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Save content to storage."""
        ...

    async def get(self, key: str) -> str | None:
        """Get content from storage."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete content from storage."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if content exists."""
        ...

    async def get_url(self, key: str) -> str:
        """Get URL for content."""
        ...


class LocalStorageRepository:
    """Local filesystem storage implementation."""

    def __init__(self, base_path: str | None = None) -> None:
        """Initialize with base path."""
        self.base_path = Path(base_path or settings.storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """Get file path for key."""
        # Sanitize key for filesystem
        sanitized_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.base_path / f"{sanitized_key}.json"

    async def save(
        self, key: str, content: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Save transcript to local storage."""
        file_path = self._get_file_path(key)

        data = StoredTranscript(
            meeting_id=key,
            content=content,
            metadata={
                "topic": metadata.get("topic", "Unknown") if metadata else "Unknown",
                "host_email": metadata.get("host_email", "Unknown") if metadata else "Unknown",
                "start_time": metadata.get("start_time", datetime.utcnow().isoformat())
                if metadata
                else datetime.utcnow().isoformat(),
                "duration": metadata.get("duration", 0) if metadata else 0,
                "stored_at": datetime.utcnow().isoformat(),
            },
        )

        async with aiofiles.open(file_path, "w") as f:
            await f.write(data.model_dump_json(indent=2))

        logger.info("Saved transcript to storage", key=key, path=str(file_path))
        return str(file_path)

    async def get(self, key: str) -> str | None:
        """Get transcript content from storage."""
        file_path = self._get_file_path(key)

        try:
            async with aiofiles.open(file_path, "r") as f:
                data = json.loads(await f.read())
                return data.get("content")
        except FileNotFoundError:
            return None

    async def get_with_metadata(self, key: str) -> StoredTranscript | None:
        """Get transcript with metadata from storage."""
        file_path = self._get_file_path(key)

        try:
            async with aiofiles.open(file_path, "r") as f:
                data = json.loads(await f.read())
                return StoredTranscript(**data)
        except FileNotFoundError:
            return None

    async def delete(self, key: str) -> bool:
        """Delete transcript from storage."""
        file_path = self._get_file_path(key)

        try:
            file_path.unlink()
            logger.info("Deleted transcript from storage", key=key)
            return True
        except FileNotFoundError:
            return False

    async def exists(self, key: str) -> bool:
        """Check if transcript exists."""
        file_path = self._get_file_path(key)
        return file_path.exists()

    async def get_url(self, key: str) -> str:
        """Get file URL for transcript."""
        file_path = self._get_file_path(key)
        return f"file://{file_path}"

    async def list_all(self) -> list[str]:
        """List all stored transcript keys."""
        return [
            f.stem for f in self.base_path.glob("*.json")
        ]


class MockS3StorageRepository:
    """Mock S3 storage for production-like interface."""

    def __init__(self, bucket: str = "meeting-transcripts") -> None:
        """Initialize with bucket name."""
        self.bucket = bucket
        self._local = LocalStorageRepository(
            str(Path(settings.storage_path) / "s3-mock" / bucket)
        )

    async def save(
        self, key: str, content: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Save to mock S3."""
        await self._local.save(key, content, metadata)
        logger.info("Saved to mock S3", bucket=self.bucket, key=key)
        return f"s3://{self.bucket}/{key}"

    async def get(self, key: str) -> str | None:
        """Get from mock S3."""
        return await self._local.get(key)

    async def delete(self, key: str) -> bool:
        """Delete from mock S3."""
        return await self._local.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if exists in mock S3."""
        return await self._local.exists(key)

    async def get_url(self, key: str) -> str:
        """Get mock pre-signed URL."""
        expires = int(datetime.utcnow().timestamp()) + 3600
        return f"https://{self.bucket}.s3.amazonaws.com/{key}?expires={expires}&signature=mock"


# Factory function to get storage repository
def get_storage_repository() -> LocalStorageRepository | MockS3StorageRepository:
    """Get storage repository based on configuration."""
    if settings.storage_type == "s3":
        return MockS3StorageRepository()
    return LocalStorageRepository()


# Singleton instance
storage_repository = get_storage_repository()
