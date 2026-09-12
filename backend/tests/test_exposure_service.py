import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories.exposure import ExposedAssetRecord
from app.schemas.exposure import AssetType
from app.services.exposure_service import ExposureService
from app.services.risk_service import RiskCellNotFoundError


class StubCellRepository:
    def __init__(self, cell):
        self.cell = cell

    async def get_by_code(self, _cell_code):
        return self.cell


class StubAssetRepository:
    def __init__(self, records=None):
        self.records = records or []
        self.query = None

    async def find_within_radius(self, cell_id, radius_m):
        self.query = (cell_id, radius_m)
        return self.records


async def assert_exposure_service_aggregates_all_asset_types() -> None:
    cell = SimpleNamespace(id=uuid4(), cell_code="A17")
    hospital = SimpleNamespace(
        id=uuid4(),
        asset_code="HOSP-1",
        name="District Hospital",
        asset_type="HOSPITAL",
        criticality=5,
        properties={"beds": 50},
    )
    asset_repository = StubAssetRepository(
        [
            ExposedAssetRecord(
                asset=hospital,
                distance_m=125.5,
                geometry={"type": "Point", "coordinates": [93.75, 27.15]},
            )
        ]
    )
    service = ExposureService(StubCellRepository(cell), asset_repository)

    response = await service.get_exposure("A17", 2_000)

    assert response.total_assets == 1
    assert response.counts[AssetType.HOSPITAL] == 1
    assert response.counts[AssetType.VILLAGE] == 0
    assert response.assets[0].properties == {"beds": 50}
    assert asset_repository.query == (cell.id, 2_000)


def test_exposure_service_aggregates_all_asset_types() -> None:
    asyncio.run(assert_exposure_service_aggregates_all_asset_types())


async def assert_exposure_service_rejects_unknown_cell() -> None:
    asset_repository = StubAssetRepository()
    service = ExposureService(StubCellRepository(None), asset_repository)

    with pytest.raises(RiskCellNotFoundError, match="missing-cell"):
        await service.get_exposure("missing-cell", 2_000)

    assert asset_repository.query is None


def test_exposure_service_rejects_unknown_cell() -> None:
    asyncio.run(assert_exposure_service_rejects_unknown_cell())
