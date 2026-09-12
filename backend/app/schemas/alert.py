from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

ActorReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class AlertSeverity(StrEnum):
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"


class AlertAction(StrEnum):
    CREATED = "CREATED"
    SUPPRESSED = "SUPPRESSED"
    REFRESHED = "REFRESHED"
    ESCALATED = "ESCALATED"


class AlertEventType(StrEnum):
    CREATED = "CREATED"
    REFRESHED = "REFRESHED"
    ESCALATED = "ESCALATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"


class AlertActorType(StrEnum):
    SYSTEM = "SYSTEM"
    CLIENT = "CLIENT"


class AlertEvaluation(BaseModel):
    alert_id: UUID
    event_id: UUID | None = None
    event_created_at: datetime | None = None
    action: AlertAction
    severity: AlertSeverity
    occurrence_count: int = Field(ge=1)


class AlertSummary(BaseModel):
    id: UUID
    cell_id: UUID
    cell_code: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    current_probability: float = Field(ge=0, le=1)
    peak_probability: float = Field(ge=0, le=1)
    drivers: list[str]
    exposure: dict[str, Any]
    occurrence_count: int = Field(ge=1)
    first_seen_at: datetime
    last_seen_at: datetime
    last_emitted_at: datetime
    created_at: datetime
    updated_at: datetime


class AlertEventResponse(BaseModel):
    id: UUID
    event_type: AlertEventType
    from_status: AlertStatus
    to_status: AlertStatus
    actor_type: AlertActorType
    actor_reference: str
    note: str | None
    created_at: datetime


class AlertDetail(AlertSummary):
    events: list[AlertEventResponse]


class AlertListResponse(BaseModel):
    items: list[AlertSummary]
    next_cursor: str | None = None


class AlertTransitionRequest(BaseModel):
    actor_reference: ActorReference
    note: str | None = Field(default=None, max_length=500)


class AlertTransitionResponse(BaseModel):
    alert_id: UUID
    previous_status: AlertStatus
    status: AlertStatus
    idempotent: bool
    event_id: UUID | None
    updated_at: datetime
