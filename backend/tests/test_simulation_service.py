import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.operations import RainfallSimulationRequest
from app.schemas.prediction import PredictionResponse, RiskLevel
from app.services.simulation_service import SimulationService

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


class StubCellRepository:
    def __init__(self) -> None:
        self.cell = SimpleNamespace(id=uuid4(), cell_code="A17")

    async def get_by_code(self, _cell_code):
        return self.cell


class StubSnapshotRepository:
    def __init__(self) -> None:
        self.snapshot = SimpleNamespace(id=uuid4(), rainfall_mm=30.0)

    async def get_latest_for_cell(self, _cell_id):
        return self.snapshot


class StubRunRepository:
    async def add(self, run):
        run.id = uuid4()
        run.created_at = NOW
        return run

    async def get(self, _run_id):
        return None


class StubRiskService:
    def __init__(self) -> None:
        self.request = None

    async def predict(self, request):
        self.request = request
        return PredictionResponse(
            snapshot_id=uuid4(),
            cell_id=uuid4(),
            cell_code=request.cell_code,
            probability=0.78,
            predicted_class=1,
            risk_level=RiskLevel.HIGH,
            rainfall_mm=request.rainfall_mm,
            drivers=["Steep slope"],
            recorded_at=NOW,
        )


class StubTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


async def assert_simulation_uses_latest_baseline_and_real_risk_service() -> None:
    risk_service = StubRiskService()
    transaction = StubTransaction()
    service = SimulationService(
        cell_repository=StubCellRepository(),
        snapshot_repository=StubSnapshotRepository(),
        run_repository=StubRunRepository(),
        risk_service=risk_service,
        transaction=transaction,
        clock=lambda: NOW,
    )

    response = await service.simulate(
        RainfallSimulationRequest(
            cell_code="A17",
            rainfall_multiplier=3,
            rainfall_7day_antecedent_mm=240,
            rainfall_event_era5_mm=135,
            soil_clay_pct=35.5,
            soil_sand_pct=28,
        )
    )

    assert response.baseline_rainfall_mm == 30
    assert response.simulated_rainfall_mm == 90
    assert risk_service.request.rainfall_mm == 90
    assert risk_service.request.rainfall_7day_antecedent_mm == 240
    assert risk_service.request.soil_clay_pct == 35.5
    assert response.prediction.risk_level == RiskLevel.HIGH
    assert transaction.commits == 2


def test_simulation_uses_latest_baseline_and_real_risk_service() -> None:
    asyncio.run(assert_simulation_uses_latest_baseline_and_real_risk_service())
