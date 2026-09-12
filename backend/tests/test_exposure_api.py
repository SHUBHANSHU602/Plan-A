from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_exposure_service
from app.main import app
from app.schemas.exposure import AssetType, ExposureResponse
from app.services.risk_service import RiskCellNotFoundError

client = TestClient(app)


def test_exposure_endpoint_returns_aggregated_contract() -> None:
    expected = ExposureResponse(
        cell_id=uuid4(),
        cell_code="A17",
        radius_m=2_000,
        total_assets=0,
        counts={asset_type: 0 for asset_type in AssetType},
        assets=[],
    )

    class StubExposureService:
        async def get_exposure(self, _cell_code, _radius_m):
            return expected

    app.dependency_overrides[get_exposure_service] = lambda: StubExposureService()
    try:
        response = client.get("/api/v1/exposure/A17?radius_m=2000")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_exposure_endpoint_maps_unknown_cell_to_404() -> None:
    class StubExposureService:
        async def get_exposure(self, cell_code, _radius_m):
            raise RiskCellNotFoundError(cell_code)

    app.dependency_overrides[get_exposure_service] = lambda: StubExposureService()
    try:
        response = client.get("/api/v1/exposure/missing-cell")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_exposure_endpoint_caps_search_radius() -> None:
    response = client.get("/api/v1/exposure/A17?radius_m=50001")

    assert response.status_code == 422
