from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.alert import AlertEventType


class NotificationChannel(StrEnum):
    DASHBOARD = "DASHBOARD"
    FCM = "FCM"


class NotificationEvent(BaseModel):
    event_id: UUID
    alert_id: UUID
    event_type: AlertEventType
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationDeliveryResult(BaseModel):
    provider: str
    channel: NotificationChannel
    delivered: bool
    error: str | None = None


class WebSocketControlMessage(BaseModel):
    type: str
