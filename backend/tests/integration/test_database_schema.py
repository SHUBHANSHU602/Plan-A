import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

pytestmark = pytest.mark.integration

if os.getenv("RUN_DATABASE_TESTS") != "1":
    pytest.skip("database integration tests are disabled", allow_module_level=True)


async def assert_database_schema() -> None:
    engine = create_async_engine(get_settings().database_url)
    cell_id = uuid4()
    snapshot_id = uuid4()

    try:
        async with engine.begin() as connection:
            postgis_version = await connection.scalar(text("SELECT PostGIS_Version()"))
            risk_cells_table = await connection.scalar(
                text("SELECT to_regclass('public.risk_cells')")
            )
            risk_snapshots_table = await connection.scalar(
                text("SELECT to_regclass('public.risk_snapshots')")
            )
            notification_subscriptions_table = await connection.scalar(
                text("SELECT to_regclass('public.notification_subscriptions')")
            )
            alert_deliveries_table = await connection.scalar(
                text("SELECT to_regclass('public.alert_deliveries')")
            )

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
                    "cell_code": "integration-cell",
                    "geometry": "POLYGON((93.7 27.1, 93.8 27.1, 93.8 27.2, 93.7 27.2, 93.7 27.1))",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO risk_snapshots (
                        id, cell_id, probability, predicted_class,
                        rainfall_mm, risk_level, drivers
                    )
                    VALUES (
                        :id, :cell_id, 0.87, 1,
                        115.34, 'CRITICAL', CAST(:drivers AS jsonb)
                    )
                    """
                ),
                {
                    "id": snapshot_id,
                    "cell_id": cell_id,
                    "drivers": '["High rainfall", "Steep slope"]',
                },
            )
            stored_probability = await connection.scalar(
                text("SELECT probability FROM risk_snapshots WHERE id = :id"),
                {"id": snapshot_id},
            )

        assert postgis_version
        assert risk_cells_table == "risk_cells"
        assert risk_snapshots_table == "risk_snapshots"
        assert notification_subscriptions_table == "notification_subscriptions"
        assert alert_deliveries_table == "alert_deliveries"
        assert stored_probability == pytest.approx(0.87)
    finally:
        await engine.dispose()


def test_postgis_migration_and_risk_persistence() -> None:
    asyncio.run(assert_database_schema())
