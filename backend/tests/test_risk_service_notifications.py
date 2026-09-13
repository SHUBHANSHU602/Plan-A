import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.models.risk import RiskSnapshot
from app.schemas.alert import AlertAction, AlertEvaluation, AlertSeverity
from app.schemas.prediction import ModelPrediction, PredictionRequest, RiskLevel
from app.services.risk_service import RiskService


class StubCellRepository:
    def __init__(self) -> None:
        self.cell = SimpleNamespace(
            id=uuid4(),
            cell_code="A17",
            elevation_m=213,
            slope_deg=50.76,
            aspect_deg=22.93,
        )

    async def get_feature_set(self, _cell_code):
        return SimpleNamespace(cell=self.cell, latitude=27.19, longitude=93.78)


class StubSnapshotRepository:
    async def save(self, snapshot: RiskSnapshot):
        snapshot.id = uuid4()
        snapshot.recorded_at = datetime.now(UTC)
        return snapshot


class StubModelGateway:
    async def predict(self, _features):
        return ModelPrediction(
            probability=0.87,
            predicted_class=1,
            drivers=["High rainfall"],
        )


class StubClassifier:
    def classify(self, _probability):
        return RiskLevel.CRITICAL


class StubAlertService:
    def __init__(self, action: AlertAction) -> None:
        self.action = action

    async def evaluate(self, _snapshot, _cell_code):
        emitted = self.action != AlertAction.SUPPRESSED
        return AlertEvaluation(
            alert_id=uuid4(),
            event_id=uuid4() if emitted else None,
            event_created_at=datetime.now(UTC) if emitted else None,
            action=self.action,
            severity=AlertSeverity.CRITICAL,
            title="Critical Landslide Risk",
            message="Elevated risk detected.",
            occurrence_count=1,
        )


class StubTransaction:
    def __init__(self, call_order) -> None:
        self.call_order = call_order

    async def commit(self):
        self.call_order.append("commit")

    async def rollback(self):
        self.call_order.append("rollback")


class StubNotificationDispatcher:
    def __init__(self, call_order) -> None:
        self.call_order = call_order
        self.events = []

    async def dispatch(self, event):
        self.call_order.append("dispatch")
        self.events.append(event)
        return []


async def run_prediction(action: AlertAction):
    call_order = []
    dispatcher = StubNotificationDispatcher(call_order)
    service = RiskService(
        cell_repository=StubCellRepository(),
        snapshot_repository=StubSnapshotRepository(),
        model_gateway=StubModelGateway(),
        classifier=StubClassifier(),
        alert_service=StubAlertService(action),
        transaction=StubTransaction(call_order),
        notification_dispatcher=dispatcher,
    )

    response = await service.predict(PredictionRequest(cell_code="A17", rainfall_mm=115.34))
    return call_order, dispatcher, response


def test_emitted_alert_is_dispatched_only_after_commit() -> None:
    call_order, dispatcher, response = asyncio.run(run_prediction(AlertAction.CREATED))

    assert call_order == ["commit", "dispatch"]
    assert dispatcher.events[0].alert_id == response.alert.alert_id
    assert dispatcher.events[0].payload["cell_code"] == "A17"


def test_suppressed_alert_is_not_dispatched() -> None:
    call_order, dispatcher, _response = asyncio.run(run_prediction(AlertAction.SUPPRESSED))

    assert call_order == ["commit"]
    assert dispatcher.events == []
