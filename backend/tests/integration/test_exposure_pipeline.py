import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.main import app

pytestmark = pytest.mark.integration

if os.getenv("RUN_DATABASE_TESTS") != "1":
    pytest.skip("database integration tests are disabled", allow_module_level=True)

cell_id = uuid4()
cell_code = f"exposure-cell-{cell_id}"


async def seed_exposure_data() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO risk_cells (id, cell_code, geometry)
                VALUES (
                    :id, :cell_code,
                    ST_GeomFromText(
                        'POLYGON((93.74 27.14, 93.76 27.14, 93.76 27.16, '
                        '93.74 27.16, 93.74 27.14))',
                        4326
                    )
                )
                """
            ),
            {"id": cell_id, "cell_code": cell_code},
        )
        await connection.execute(
            text(
                """
                INSERT INTO assets (
                    id, asset_code, name, asset_type, criticality, geometry, properties
                )
                VALUES
                    (
                        :hospital_id, :hospital_code, 'District Hospital', 'HOSPITAL', 5,
                        ST_GeomFromText('POINT(93.75 27.15)', 4326),
                        '{"beds": 50}'::jsonb
                    ),
                    (
                        :village_id, :village_code, 'Nearby Village', 'VILLAGE', 4,
                        ST_GeomFromText('POINT(93.77 27.15)', 4326),
                        '{}'::jsonb
                    ),
                    (
                        :road_id, :road_code, 'Distant Road', 'ROAD', 3,
                        ST_GeomFromText('LINESTRING(94.0 27.1, 94.0 27.2)', 4326),
                        '{}'::jsonb
                    )
                """
            ),
            {
                "hospital_id": uuid4(),
                "hospital_code": f"hospital-{cell_id}",
                "village_id": uuid4(),
                "village_code": f"village-{cell_id}",
                "road_id": uuid4(),
                "road_code": f"road-{cell_id}",
            },
        )


async def assert_exposure_pipeline() -> None:
    try:
        await seed_exposure_data()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/exposure/{cell_code}?radius_m=2000")

        assert response.status_code == 200
        payload = response.json()
        assert payload["cell_code"] == cell_code
        assert payload["total_assets"] == 2
        assert payload["counts"]["HOSPITAL"] == 1
        assert payload["counts"]["VILLAGE"] == 1
        assert payload["counts"]["ROAD"] == 0
        assert [asset["asset_type"] for asset in payload["assets"]] == [
            "HOSPITAL",
            "VILLAGE",
        ]
        assert payload["assets"][0]["distance_m"] == pytest.approx(0)
        assert payload["assets"][1]["distance_m"] < 2_000
        assert payload["assets"][1]["geometry"]["type"] == "Point"
    finally:
        await engine.dispose()


def test_exposure_pipeline_uses_postgis_meter_distance() -> None:
    asyncio.run(assert_exposure_pipeline())
