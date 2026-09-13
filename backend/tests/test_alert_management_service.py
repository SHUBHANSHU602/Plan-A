import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories.alert import AlertRecord
from app.schemas.alert import AlertSeverity, AlertStatus, AlertTransitionRequest
from app.services.alert_management_service import (
    AlertManagementService,
    InvalidAlertCursorError,
    InvalidAlertTransitionError,
)


class StubAlertRepository:
    def __init__(self, alert=None, records=None) -> None:
        self.alert = alert
        self.records = records or []
        self.list_arguments = None

    async def get_for_update(self, _alert_id):
        return self.alert

    async def save(self, alert):
        self.alert = alert
        return alert

    async def list_records(self, **kwargs):
        self.list_arguments = kwargs
        return self.records

    async def get_record(self, _alert_id):
        if self.alert is None:
            return None
        return AlertRecord(alert=self.alert, cell_code="A17")


class StubEventRepository:
    def __init__(self) -> None:
        self.events = []

    async def add(self, event):
        event.id = event.id or uuid4()
        event.created_at = event.created_at or datetime.now(UTC)
        self.events.append(event)
        return event

    async def list_for_alert(self, _alert_id):
        return self.events


class StubTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class StubNotificationDispatcher:
    def __init__(self, transaction: StubTransaction) -> None:
        self.transaction = transaction
        self.events = []
        self.commit_counts = []

    async def dispatch(self, event):
        self.events.append(event)
        self.commit_counts.append(self.transaction.commits)
        return []


def make_alert(status="ACTIVE", last_seen_at=None):
    now = last_seen_at or datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        cell_id=uuid4(),
        severity="CRITICAL",
        status=status,
        title="Critical Landslide Risk",
        message="Elevated risk detected.",
        current_probability=0.87,
        peak_probability=0.90,
        drivers=["High rainfall"],
        exposure={"total_assets": 1},
        occurrence_count=2,
        first_seen_at=now - timedelta(minutes=10),
        last_seen_at=now,
        last_emitted_at=now,
        created_at=now - timedelta(minutes=10),
        updated_at=now,
    )


async def assert_lifecycle_is_guarded_and_idempotent() -> None:
    alert = make_alert()
    repository = StubAlertRepository(alert=alert)
    events = StubEventRepository()
    transaction = StubTransaction()
    notifications = StubNotificationDispatcher(transaction)
    service = AlertManagementService(repository, events, transaction, notifications)
    request = AlertTransitionRequest(actor_reference="  district-admin  ", note="Reviewed")

    acknowledged = await service.transition(alert.id, AlertStatus.ACKNOWLEDGED, request)
    repeated = await service.transition(alert.id, AlertStatus.ACKNOWLEDGED, request)

    assert acknowledged.status == AlertStatus.ACKNOWLEDGED
    assert acknowledged.idempotent is False
    assert repeated.idempotent is True
    assert len(events.events) == 1
    assert events.events[0].actor_reference == "district-admin"
    assert transaction.commits == 2
    assert [event.event_type for event in notifications.events] == ["ACKNOWLEDGED"]
    assert notifications.commit_counts == [1]

    with pytest.raises(InvalidAlertTransitionError):
        await service.transition(alert.id, AlertStatus.RESOLVED, request)

    assert transaction.rollbacks == 1
    assert alert.status == "ACKNOWLEDGED"


def test_lifecycle_is_guarded_and_idempotent() -> None:
    asyncio.run(assert_lifecycle_is_guarded_and_idempotent())


async def assert_cursor_pagination_is_stable() -> None:
    newer = AlertRecord(
        alert=make_alert(last_seen_at=datetime(2026, 9, 12, 11, tzinfo=UTC)),
        cell_code="A1",
    )
    older = AlertRecord(
        alert=make_alert(last_seen_at=datetime(2026, 9, 12, 10, tzinfo=UTC)),
        cell_code="A2",
    )
    repository = StubAlertRepository(records=[newer, older])
    transaction = StubTransaction()
    service = AlertManagementService(
        repository,
        StubEventRepository(),
        transaction,
        StubNotificationDispatcher(transaction),
    )

    page = await service.list_alerts(
        status=AlertStatus.ACTIVE,
        severity=AlertSeverity.CRITICAL,
        cell_code=None,
        cursor=None,
        limit=1,
    )

    assert [item.cell_code for item in page.items] == ["A1"]
    assert page.next_cursor is not None
    decoded = service._decode_cursor(page.next_cursor)
    assert decoded == (newer.alert.created_at, newer.alert.id)
    assert repository.list_arguments["limit"] == 2


def test_cursor_pagination_is_stable() -> None:
    asyncio.run(assert_cursor_pagination_is_stable())


async def assert_invalid_cursor_is_rejected() -> None:
    transaction = StubTransaction()
    service = AlertManagementService(
        StubAlertRepository(),
        StubEventRepository(),
        transaction,
        StubNotificationDispatcher(transaction),
    )

    with pytest.raises(InvalidAlertCursorError):
        await service.list_alerts(
            status=None,
            severity=None,
            cell_code=None,
            cursor="not-a-valid-cursor",
            limit=50,
        )


def test_invalid_cursor_is_rejected() -> None:
    asyncio.run(assert_invalid_cursor_is_rejected())
