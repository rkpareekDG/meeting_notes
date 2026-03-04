"""Admin routes for system management."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.repositories import (
    idempotency_repository,
    jira_ticket_repository,
    storage_repository,
    user_mapping_repository,
)
from app.repositories.user_mapping import UserMapping
from app.services import queue_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class UserMappingCreate(BaseModel):
    """User mapping creation request."""

    email: str
    zoom_user_id: str | None = None
    slack_user_id: str | None = None
    jira_account_id: str | None = None
    microsoft_user_id: str | None = None
    display_name: str | None = None


class UserMappingResponse(BaseModel):
    """User mapping response."""

    email: str
    zoom_user_id: str | None
    slack_user_id: str | None
    jira_account_id: str | None
    microsoft_user_id: str | None
    display_name: str | None


# User Mapping endpoints
@router.post("/user-mappings", response_model=UserMappingResponse)
async def create_user_mapping(data: UserMappingCreate) -> UserMappingResponse:
    """Create or update user mapping.

    Args:
        data: User mapping data

    Returns:
        Created/updated mapping
    """
    mapping = UserMapping(
        email=data.email,
        zoom_user_id=data.zoom_user_id,
        slack_user_id=data.slack_user_id,
        jira_account_id=data.jira_account_id,
        microsoft_user_id=data.microsoft_user_id,
        display_name=data.display_name,
    )

    await user_mapping_repository.save(mapping)

    return UserMappingResponse(
        email=mapping.email,
        zoom_user_id=mapping.zoom_user_id,
        slack_user_id=mapping.slack_user_id,
        jira_account_id=mapping.jira_account_id,
        microsoft_user_id=mapping.microsoft_user_id,
        display_name=mapping.display_name,
    )


@router.get("/user-mappings", response_model=list[UserMappingResponse])
async def list_user_mappings() -> list[UserMappingResponse]:
    """List all user mappings.

    Returns:
        List of mappings
    """
    mappings = await user_mapping_repository.get_all()
    return [
        UserMappingResponse(
            email=m.email,
            zoom_user_id=m.zoom_user_id,
            slack_user_id=m.slack_user_id,
            jira_account_id=m.jira_account_id,
            microsoft_user_id=m.microsoft_user_id,
            display_name=m.display_name,
        )
        for m in mappings
    ]


@router.get("/user-mappings/{email}", response_model=UserMappingResponse)
async def get_user_mapping(email: str) -> UserMappingResponse:
    """Get user mapping by email.

    Args:
        email: User email

    Returns:
        User mapping
    """
    mapping = await user_mapping_repository.get_by_email(email)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User mapping not found: {email}",
        )

    return UserMappingResponse(
        email=mapping.email,
        zoom_user_id=mapping.zoom_user_id,
        slack_user_id=mapping.slack_user_id,
        jira_account_id=mapping.jira_account_id,
        microsoft_user_id=mapping.microsoft_user_id,
        display_name=mapping.display_name,
    )


@router.delete("/user-mappings/{email}")
async def delete_user_mapping(email: str) -> dict[str, Any]:
    """Delete user mapping.

    Args:
        email: User email

    Returns:
        Deletion result
    """
    deleted = await user_mapping_repository.delete(email)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User mapping not found: {email}",
        )

    return {"deleted": True, "email": email}


# Queue management endpoints
@router.get("/queue/stats")
async def get_queue_stats() -> dict[str, Any]:
    """Get queue statistics.

    Returns:
        Queue stats
    """
    return queue_service.get_stats()


@router.get("/queue/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Get job details.

    Args:
        job_id: Job ID

    Returns:
        Job details
    """
    job = await queue_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return {
        "id": job.id,
        "name": job.name,
        "status": job.status.value,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error": job.error,
    }


@router.post("/queue/clear-completed")
async def clear_completed_jobs(older_than_hours: int = 24) -> dict[str, Any]:
    """Clear completed jobs.

    Args:
        older_than_hours: Age threshold in hours

    Returns:
        Clear result
    """
    count = await queue_service.clear_completed(older_than_hours)
    return {"cleared": count, "older_than_hours": older_than_hours}


# Idempotency management
@router.get("/idempotency/{key}")
async def get_idempotency_key(key: str) -> dict[str, Any]:
    """Get idempotency key status.

    Args:
        key: Idempotency key

    Returns:
        Key status
    """
    exists = await idempotency_repository.exists(key)
    value = await idempotency_repository.get(key)
    return {"key": key, "exists": exists, "value": value}


@router.delete("/idempotency/{key}")
async def delete_idempotency_key(key: str) -> dict[str, Any]:
    """Delete idempotency key.

    Args:
        key: Idempotency key

    Returns:
        Deletion result
    """
    await idempotency_repository.delete(key)
    return {"deleted": True, "key": key}


# Meeting data endpoints
@router.get("/meetings/{meeting_id}/tickets")
async def get_meeting_tickets(meeting_id: str) -> dict[str, Any]:
    """Get Jira tickets for a meeting.

    Args:
        meeting_id: Meeting ID

    Returns:
        Tickets created for meeting
    """
    tickets = await jira_ticket_repository.get_by_meeting(meeting_id)
    return {
        "meeting_id": meeting_id,
        "tickets": [
            {
                "jira_key": t.jira_key,
                "jira_id": t.jira_id,
                "created_at": t.created_at.isoformat(),
            }
            for t in tickets
        ],
    }


@router.get("/meetings/{meeting_id}/transcript")
async def get_meeting_transcript(meeting_id: str) -> dict[str, Any]:
    """Get transcript for a meeting.

    Args:
        meeting_id: Meeting ID

    Returns:
        Transcript data
    """
    transcript = await storage_repository.get_transcript(meeting_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found: {meeting_id}",
        )

    return {
        "meeting_id": meeting_id,
        "transcript": transcript,
    }
