"""Queue service for background job processing."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import uuid4

from app.utils.logger import get_logger

logger = get_logger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Job:
    """Background job definition."""

    id: str
    name: str
    data: dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: Any = None


class QueueService:
    """Simple in-memory queue service for background processing."""

    def __init__(self) -> None:
        """Initialize queue service."""
        self._jobs: dict[str, Job] = {}
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._is_running = False
        self._worker_task: asyncio.Task[None] | None = None

    def register_handler(
        self,
        job_name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """Register a job handler.

        Args:
            job_name: Name of job type
            handler: Async function to handle job
        """
        self._handlers[job_name] = handler
        logger.info("Registered job handler", job_name=job_name)

    async def add_job(
        self,
        name: str,
        data: dict[str, Any],
        max_attempts: int = 3,
    ) -> Job:
        """Add a job to the queue.

        Args:
            name: Job type name
            data: Job data
            max_attempts: Maximum retry attempts

        Returns:
            Created job
        """
        job = Job(
            id=str(uuid4()),
            name=name,
            data=data,
            max_attempts=max_attempts,
        )

        self._jobs[job.id] = job
        await self._queue.put(job.id)

        logger.info("Added job to queue", job_id=job.id, job_name=name)
        return job

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job or None
        """
        return self._jobs.get(job_id)

    async def start(self) -> None:
        """Start the queue worker."""
        if self._is_running:
            return

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Queue worker started")

    async def stop(self) -> None:
        """Stop the queue worker."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Queue worker stopped")

    async def _worker(self) -> None:
        """Background worker that processes jobs."""
        while self._is_running:
            try:
                # Wait for job with timeout
                try:
                    job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                job = self._jobs.get(job_id)
                if not job:
                    logger.warning("Job not found", job_id=job_id)
                    continue

                await self._process_job(job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker error", error=str(e))

    async def _process_job(self, job: Job) -> None:
        """Process a single job.

        Args:
            job: Job to process
        """
        handler = self._handlers.get(job.name)
        if not handler:
            logger.error("No handler for job", job_name=job.name)
            job.status = JobStatus.FAILED
            job.error = f"No handler registered for {job.name}"
            return

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.attempts += 1

        logger.info(
            "Processing job",
            job_id=job.id,
            job_name=job.name,
            attempt=job.attempts,
        )

        try:
            job.result = await handler(job.data)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            logger.info(
                "Job completed",
                job_id=job.id,
                duration_ms=(job.completed_at - job.started_at).total_seconds() * 1000,
            )

        except Exception as e:
            logger.error(
                "Job failed",
                job_id=job.id,
                error=str(e),
                attempt=job.attempts,
            )

            job.error = str(e)

            if job.attempts < job.max_attempts:
                job.status = JobStatus.RETRYING
                # Exponential backoff
                delay = 2 ** job.attempts
                await asyncio.sleep(delay)
                await self._queue.put(job.id)
            else:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()

    def get_stats(self) -> dict[str, int]:
        """Get queue statistics.

        Returns:
            Stats dictionary
        """
        stats = {
            "total": len(self._jobs),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "retrying": 0,
        }

        for job in self._jobs.values():
            if job.status == JobStatus.PENDING:
                stats["pending"] += 1
            elif job.status == JobStatus.PROCESSING:
                stats["processing"] += 1
            elif job.status == JobStatus.COMPLETED:
                stats["completed"] += 1
            elif job.status == JobStatus.FAILED:
                stats["failed"] += 1
            elif job.status == JobStatus.RETRYING:
                stats["retrying"] += 1

        return stats

    async def clear_completed(self, older_than_hours: int = 24) -> int:
        """Clear completed jobs older than specified hours.

        Args:
            older_than_hours: Age threshold

        Returns:
            Number of cleared jobs
        """
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(hours=older_than_hours)
        to_delete = []

        for job_id, job in self._jobs.items():
            if (
                job.status == JobStatus.COMPLETED
                and job.completed_at
                and job.completed_at < threshold
            ):
                to_delete.append(job_id)

        for job_id in to_delete:
            del self._jobs[job_id]

        logger.info("Cleared completed jobs", count=len(to_delete))
        return len(to_delete)


# Singleton instance
queue_service = QueueService()
