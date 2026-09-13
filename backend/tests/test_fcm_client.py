import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from firebase_admin import messaging

from app.notifications.fcm_client import FirebaseAdminClient, PushDeliveryError
from app.schemas.alert import AlertEventType
from app.schemas.notification import NotificationEvent


def make_event() -> NotificationEvent:
    return NotificationEvent(
        event_id=uuid4(),
        alert_id=uuid4(),
        event_type=AlertEventType.CREATED,
        occurred_at=datetime.now(UTC),
        payload={
            "title": "Critical Landslide Risk",
            "message": "Elevated risk detected.",
            "cell_code": "A17",
            "severity": "CRITICAL",
            "status": "ACTIVE",
        },
    )


def make_client() -> FirebaseAdminClient:
    client = FirebaseAdminClient.__new__(FirebaseAdminClient)
    client._app = object()
    return client


def test_firebase_client_builds_notification_and_data_payload(monkeypatch) -> None:
    captured = {}

    def fake_send(message, *, app):
        captured["message"] = message
        captured["app"] = app
        return "projects/test/messages/123"

    monkeypatch.setattr(messaging, "send", fake_send)
    client = make_client()

    result = asyncio.run(client.send("firebase-installation-id", make_event()))

    assert result == "projects/test/messages/123"
    assert captured["message"].fid == "firebase-installation-id"
    assert captured["message"].notification.title == "Critical Landslide Risk"
    assert captured["message"].data["cell_code"] == "A17"
    assert captured["app"] is client._app


def test_firebase_client_classifies_invalid_target(monkeypatch) -> None:
    class UnregisteredError(Exception):
        pass

    def fake_send(_message, *, app):
        raise UnregisteredError("target is no longer registered")

    monkeypatch.setattr(messaging, "send", fake_send)

    with pytest.raises(PushDeliveryError) as captured:
        asyncio.run(make_client().send("firebase-installation-id", make_event()))

    assert captured.value.invalid_target is True
    assert captured.value.retryable is False
