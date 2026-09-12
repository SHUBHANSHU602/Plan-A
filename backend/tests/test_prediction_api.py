from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_risk_service
from app.main import app
from app.schemas.prediction import PredictionResponse, RiskLevel

client = TestClient(app)


def test_prediction_endpoint_returns_persisted_risk_contract() -> None:
    expected = PredictionResponse(
        snapshot_id=uuid4(),
        cell_id=uuid4(),
        cell_code="A17",
        probability=0.87,
        predicted_class=1,
        risk_level=RiskLevel.CRITICAL,
        rainfall_mm=115.34,
        drivers=["High rainfall", "Steep slope"],
        recorded_at=datetime.now(UTC),
    )

    class StubRiskService:
        async def predict(self, _request):
            return expected

    app.dependency_overrides[get_risk_service] = lambda: StubRiskService()
    try:
        response = client.post(
            "/api/v1/predict",
            json={"cell_code": "A17", "rainfall_mm": 115.34},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == expected.model_dump(mode="json")


def test_prediction_request_rejects_negative_rainfall() -> None:
    response = client.post(
        "/api/v1/predict",
        json={"cell_code": "A17", "rainfall_mm": -1},
    )

    assert response.status_code == 422
