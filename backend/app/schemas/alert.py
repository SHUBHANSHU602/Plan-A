from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


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


class AlertEvaluation(BaseModel):
    alert_id: UUID
    action: AlertAction
    severity: AlertSeverity
    occurrence_count: int = Field(ge=1)
