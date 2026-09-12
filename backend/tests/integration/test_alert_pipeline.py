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
cell_code = f"alert-cell-{cell_id}"


async def seed_alert_data() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO risk_cells (
                    id, cell_code, geometry, elevation_m, slope_deg, aspect_deg
                )
                VALUES (
                    :id, :cell_code,
                    ST_GeomFromText(
                        'POLYGON((93.74 27.14, 93.76 27.14, 93.76 27.16, '
                        '93.74 27.16, 93.74 27.14))',
                        4326
                    ),
                    213, 50.76, 22.93
                )
                """
            ),
            {"id": cell_id, "cell_code": cell_code},
        )
        await connection.execute(
            text(
                """
                INSERT INTO assets (
                    id, asset_code, name, asset_type, criticality, geometry
                )
                VALUES (
                    :id, :asset_code, 'Alert Test Hospital', 'HOSPITAL', 5,
                    ST_GeomFromText('POINT(93.75 27.15)', 4326)
                )
                """
            ),
            {"id": uuid4(), "asset_code": f"alert-hospital-{cell_id}"},
        )


async def read_alert_state() -> dict:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT severity, status, occurrence_count, peak_probability, exposure
                    FROM alerts
                    WHERE cell_id = :cell_id
                    """
                ),
                {"cell_id": cell_id},
            )
        ).one()
        count = await connection.scalar(
            text("SELECT count(*) FROM alerts WHERE cell_id = :cell_id"),
            {"cell_id": cell_id},
        )
        return {**dict(row._mapping), "count": count}


async def assert_concurrent_alert_deduplication() -> None:
    try:
        await seed_alert_data()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            responses = await asyncio.gather(
                client.post(
                    "/api/v1/predict",
                    json={"cell_code": cell_code, "rainfall_mm": 115.34},
                ),
                client.post(
                    "/api/v1/predict",
                    json={"cell_code": cell_code, "rainfall_mm": 116.0},
                ),
            )

        assert all(response.status_code == 201 for response in responses)
        actions = sorted(response.json()["alert"]["action"] for response in responses)
        assert actions == ["CREATED", "SUPPRESSED"]

        stored = await read_alert_state()
        assert stored["count"] == 1
        assert stored["status"] == "ACTIVE"
        assert stored["severity"] == "CRITICAL"
        assert stored["occurrence_count"] == 2
        assert stored["peak_probability"] == pytest.approx(0.87)
        assert stored["exposure"]["total_assets"] == 1
        assert stored["exposure"]["critical_assets"] == 1
    finally:
        await engine.dispose()


def test_concurrent_predictions_create_one_open_alert() -> None:
    asyncio.run(assert_concurrent_alert_deduplication())
