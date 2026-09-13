from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints


class SubscriptionPlatform(StrEnum):
    WEB = "WEB"
    ANDROID = "ANDROID"
    IOS = "IOS"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    RETRY = "RETRY"
    SENT = "SENT"
    FAILED = "FAILED"
    INVALID_TARGET = "INVALID_TARGET"


RegistrationIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=20, max_length=4096),
]
SubscriberReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class NotificationSubscriptionCreate(BaseModel):
    registration_id: RegistrationIdentifier
    platform: SubscriptionPlatform
    subscriber_reference: SubscriberReference


class NotificationSubscriptionResponse(BaseModel):
    id: UUID
    platform: SubscriptionPlatform
    subscriber_reference: str
    active: bool
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class AlertDeliveryResponse(BaseModel):
    id: UUID
    alert_id: UUID
    alert_event_id: UUID
    subscription_id: UUID | None
    provider: str
    channel: str
    status: DeliveryStatus
    attempt_count: int = Field(ge=0)
    next_attempt_at: datetime | None
    provider_message_id: str | None
    last_error: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertDeliveryListResponse(BaseModel):
    items: list[AlertDeliveryResponse]


class StoredNotificationPayload(BaseModel):
    event_id: UUID
    alert_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]
