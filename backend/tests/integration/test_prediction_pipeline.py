import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.main import app

pytestmark = pytest.mark.integration

if os.getenv("RUN_DATABASE_TESTS") != "1":
    pytest.skip("database integration tests are disabled", allow_module_level=True)

cell_id = uuid4()
cell_code = f"prediction-cell-{cell_id}"


async def seed_risk_cell() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO risk_cells (
                    id, cell_code, geometry, elevation_m, slope_deg, aspect_deg
                )
                VALUES (
                    :id, :cell_code,
                    ST_GeomFromText(:geometry, 4326),
                    213, 50.76, 22.93
                )
                """
            ),
            {
                "id": cell_id,
                "cell_code": cell_code,
                "geometry": "POLYGON((93.7 27.1, 93.8 27.1, 93.8 27.2, 93.7 27.2, 93.7 27.1))",
            },
        )


async def read_snapshot(snapshot_id: UUID) -> dict:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT probability, predicted_class, risk_level, rainfall_mm, drivers
                    FROM risk_snapshots
                    WHERE id = :snapshot_id
                    """
                ),
                {"snapshot_id": snapshot_id},
            )
        ).one()
        return dict(row._mapping)


async def assert_prediction_pipeline() -> None:
    try:
        await seed_risk_cell()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/predict",
                json={"cell_code": cell_code, "rainfall_mm": 115.34},
            )
            missing_response = await client.post(
                "/api/v1/predict",
                json={"cell_code": "missing-cell", "rainfall_mm": 10},
            )

        assert response.status_code == 201
        payload = response.json()
        assert payload["probability"] == pytest.approx(0.87)
        assert payload["predicted_class"] == 1
        assert payload["risk_level"] == "CRITICAL"
        assert payload["drivers"] == ["High rainfall", "Steep slope"]
        assert missing_response.status_code == 404

        stored = await read_snapshot(UUID(payload["snapshot_id"]))
        assert stored["probability"] == pytest.approx(0.87)
        assert stored["risk_level"] == "CRITICAL"
        assert stored["rainfall_mm"] == pytest.approx(115.34)
    finally:
        await engine.dispose()


def test_prediction_pipeline_reads_cell_and_persists_snapshot() -> None:
    asyncio.run(assert_prediction_pipeline())
