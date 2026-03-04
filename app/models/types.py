"""Type definitions and Pydantic models for the AI Meeting Bot."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Zoom Types
# ============================================================================


class ZoomRecordingFile(BaseModel):
    """Zoom recording file model."""

    id: str | None = None
    meeting_id: str | None = None
    recording_start: str | None = None
    recording_end: str | None = None
    file_type: str | None = None
    file_extension: str | None = None
    file_size: int | None = None
    download_url: str | None = None
    status: str | None = None
    recording_type: str | None = None


class ZoomRecordingObject(BaseModel):
    """Zoom recording object model."""

    id: str | None = None
    uuid: str | None = None
    host_id: str | None = None
    host_email: str | None = None
    topic: str | None = None
    type: int | None = None
    start_time: str | None = None
    timezone: str | None = None
    duration: int | None = None
    recording_files: list[ZoomRecordingFile] | None = []


class ZoomPayloadObject(BaseModel):
    """Zoom webhook payload object."""

    object: ZoomRecordingObject | None = None


class ZoomWebhookPayload(BaseModel):
    """Zoom webhook payload model."""

    event: str
    event_ts: int | None = None
    payload: ZoomPayloadObject

    class Config:
        extra = "allow"


class ZoomUrlValidationPayload(BaseModel):
    """Zoom URL validation payload."""

    plain_token: str = Field(..., alias="plainToken")


# ============================================================================
# LLM Types
# ============================================================================


class ActionItem(BaseModel):
    """Action item extracted from meeting."""

    task: str
    owner_name: str
    owner_email: str | None = None
    deadline: str | None = None
    priority: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    context: str | None = None

    class Config:
        populate_by_name = True


class MeetingSummary(BaseModel):
    """Meeting summary from LLM."""

    summary: str
    key_points: list[str] = []
    decisions: list[str] = []
    action_items: list[ActionItem] = []
    follow_ups: list[str] = []

    class Config:
        populate_by_name = True


class ProcessedTranscript(BaseModel):
    """Processed meeting transcript."""

    lines: list[dict[str, Any]] = []
    full_text: str = ""
    speakers: list[str] = []
    duration_seconds: int | None = None


# ============================================================================
# Calendar/Outlook Types
# ============================================================================


class AvailabilityStatus(str, Enum):
    """Calendar availability status."""

    AVAILABLE = "available"
    BUSY = "busy"
    OOF = "oof"
    UNKNOWN = "unknown"


class AvailabilityCheckResult(BaseModel):
    """Result of availability check for an action item owner."""

    email: str
    owner_name: str
    is_available: bool
    status: AvailabilityStatus
    original_deadline: str | None = None
    suggested_date: str | None = None
    warning: str | None = None


class ScheduleItem(BaseModel):
    """Calendar schedule item."""

    status: str
    start: dict[str, str]
    end: dict[str, str]
    subject: str | None = None
    location: str | None = None


class ScheduleInformation(BaseModel):
    """Calendar schedule information."""

    schedule_id: str = Field(..., alias="scheduleId")
    availability_view: str = Field(..., alias="availabilityView")
    schedule_items: list[ScheduleItem] = Field(default=[], alias="scheduleItems")
    working_hours: dict[str, Any] | None = Field(default=None, alias="workingHours")

    class Config:
        populate_by_name = True


# ============================================================================
# Jira Types
# ============================================================================


class JiraCreateResponse(BaseModel):
    """Jira issue creation response."""

    id: str
    key: str
    self: str


class JiraTicketResult(BaseModel):
    """Result of Jira ticket creation."""

    action_item: str
    jira_key: str
    success: bool
    error: str | None = None


# ============================================================================
# Storage Types
# ============================================================================


class StoredTranscript(BaseModel):
    """Stored transcript with metadata."""

    meeting_id: str
    content: str
    metadata: dict[str, Any]


# ============================================================================
# Meeting Processing Types
# ============================================================================


class MeetingProcessingResult(BaseModel):
    """Complete meeting processing result."""

    meeting_id: str
    meeting_topic: str
    host_email: str
    transcript_url: str
    summary: MeetingSummary
    availability_results: list[AvailabilityCheckResult]
    processed_at: datetime
    consent_given: bool


# ============================================================================
# Queue Types
# ============================================================================


class JobStatus(str, Enum):
    """Background job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QueueJob(BaseModel):
    """Background queue job."""

    id: str
    type: str
    payload: dict[str, Any]
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime
    processed_at: datetime | None = None
    error: str | None = None
    status: JobStatus = JobStatus.PENDING


# ============================================================================
# Idempotency Types
# ============================================================================


class IdempotencyStatus(str, Enum):
    """Idempotency record status."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IdempotencyRecord(BaseModel):
    """Idempotency record for preventing duplicate processing."""

    key: str
    status: IdempotencyStatus
    result: Any | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


# ============================================================================
# Slack Types
# ============================================================================


class SlackUserMapping(BaseModel):
    """Slack user to email mapping."""

    slack_user_id: str
    email: str
    display_name: str
