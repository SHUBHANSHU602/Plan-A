import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.models.risk import RiskSnapshot
from app.repositories.exposure import ExposedAssetRecord
from app.schemas.alert import AlertAction, AlertSeverity
from app.services.alert_policy import AlertPolicy
from app.services.alert_service import AlertService


class StubAlertRepository:
    def __init__(self) -> None:
        self.alert = None
        self.locked_cells = []

    async def lock_cell(self, cell_id):
        self.locked_cells.append(cell_id)

    async def get_open_for_update(self, _cell_id):
        return self.alert

    async def save(self, alert):
        if alert.id is None:
            alert.id = uuid4()
        self.alert = alert
        return alert


class StubAlertEventRepository:
    def __init__(self) -> None:
        self.events = []

    async def add(self, event):
        if event.id is None:
            event.id = uuid4()
        self.events.append(event)
        return event


class StubAssetRepository:
    def __init__(self, records=None) -> None:
        self.records = records or []

    async def find_within_radius(self, _cell_id, _radius_m):
        return self.records


def make_snapshot(risk_level: str, probability: float) -> RiskSnapshot:
    return RiskSnapshot(
        id=uuid4(),
        cell_id=uuid4(),
        probability=probability,
        predicted_class=1,
        rainfall_mm=115.34,
        risk_level=risk_level,
        drivers=["High rainfall"],
    )


def make_service(repository, now, records=None) -> tuple[AlertService, StubAlertEventRepository]:
    event_repository = StubAlertEventRepository()
    service = AlertService(
        repository=repository,
        event_repository=event_repository,
        asset_repository=StubAssetRepository(records),
        policy=AlertPolicy(),
        exposure_radius_m=2_000,
        dedup_cooldown=timedelta(minutes=30),
        clock=lambda: now,
    )
    return service, event_repository


async def assert_low_risk_does_not_touch_alert_storage() -> None:
    repository = StubAlertRepository()
    service, event_repository = make_service(repository, datetime(2026, 9, 12, tzinfo=UTC))

    result = await service.evaluate(make_snapshot("MEDIUM", 0.50), "A17")

    assert result is None
    assert repository.locked_cells == []
    assert repository.alert is None
    assert event_repository.events == []


def test_low_risk_does_not_touch_alert_storage() -> None:
    asyncio.run(assert_low_risk_does_not_touch_alert_storage())


async def assert_repeated_and_escalated_alert_actions() -> None:
    now = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    repository = StubAlertRepository()
    hospital = SimpleNamespace(asset_type="HOSPITAL", criticality=5)
    records = [ExposedAssetRecord(asset=hospital, distance_m=0, geometry={})]
    service, event_repository = make_service(repository, now, records)
    cell_id = uuid4()

    first_snapshot = make_snapshot("HIGH", 0.70)
    first_snapshot.cell_id = cell_id
    first = await service.evaluate(first_snapshot, "A17")

    repeated_snapshot = make_snapshot("HIGH", 0.72)
    repeated_snapshot.cell_id = cell_id
    repeated = await service.evaluate(repeated_snapshot, "A17")

    critical_snapshot = make_snapshot("CRITICAL", 0.87)
    critical_snapshot.cell_id = cell_id
    escalated = await service.evaluate(critical_snapshot, "A17")

    assert first.action == AlertAction.CREATED
    assert first.event_id == event_repository.events[0].id
    assert repeated.action == AlertAction.SUPPRESSED
    assert repeated.event_id is None
    assert escalated.action == AlertAction.ESCALATED
    assert escalated.event_id == event_repository.events[1].id
    assert escalated.severity == AlertSeverity.CRITICAL
    assert repository.alert.occurrence_count == 3
    assert repository.alert.peak_probability == 0.87
    assert repository.alert.exposure["critical_assets"] == 1
    assert [event.event_type for event in event_repository.events] == [
        "CREATED",
        "ESCALATED",
    ]


def test_repeated_alert_is_suppressed_but_escalation_is_immediate() -> None:
    asyncio.run(assert_repeated_and_escalated_alert_actions())


async def assert_alert_refreshes_after_cooldown() -> None:
    first_seen = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
    repository = StubAlertRepository()
    first_service, _ = make_service(repository, first_seen)
    first = await first_service.evaluate(
        make_snapshot("HIGH", 0.70),
        "A17",
    )

    refresh_service, refresh_events = make_service(repository, first_seen + timedelta(minutes=31))
    refreshed = await refresh_service.evaluate(
        make_snapshot("HIGH", 0.74),
        "A17",
    )

    assert first.action == AlertAction.CREATED
    assert refreshed.action == AlertAction.REFRESHED
    assert repository.alert.last_emitted_at == first_seen + timedelta(minutes=31)
    assert refresh_events.events[0].event_type == "REFRESHED"


def test_alert_refreshes_after_cooldown() -> None:
    asyncio.run(assert_alert_refreshes_after_cooldown())
