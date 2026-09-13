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
cell_code = f"lifecycle-cell-{cell_id}"


async def seed_lifecycle_cell() -> None:
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
                        'POLYGON((86.00 25.00, 86.02 25.00, 86.02 25.02, '
                        '86.00 25.02, 86.00 25.00))',
                        4326
                    ),
                    213, 50.76, 22.93
                )
                """
            ),
            {"id": cell_id, "cell_code": cell_code},
        )


async def assert_alert_lifecycle_api() -> None:
    try:
        await seed_lifecycle_cell()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            prediction = await client.post(
                "/api/v1/predict",
                json={"cell_code": cell_code, "rainfall_mm": 115.34},
            )
            assert prediction.status_code == 201
            alert_id = UUID(prediction.json()["alert"]["alert_id"])

            listed = await client.get(
                "/api/v1/alerts",
                params={
                    "status": "ACTIVE",
                    "severity": "CRITICAL",
                    "cell_code": cell_code,
                },
            )
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()["items"]] == [str(alert_id)]

            invalid_verify = await client.post(
                f"/api/v1/alerts/{alert_id}/verify",
                json={"actor_reference": "district-admin"},
            )
            assert invalid_verify.status_code == 409

            acknowledged = await client.post(
                f"/api/v1/alerts/{alert_id}/acknowledge",
                json={"actor_reference": " district-admin ", "note": "Reviewed"},
            )
            repeated = await client.post(
                f"/api/v1/alerts/{alert_id}/acknowledge",
                json={"actor_reference": "district-admin"},
            )
            verified = await client.post(
                f"/api/v1/alerts/{alert_id}/verify",
                json={"actor_reference": "field-officer", "note": "Crack confirmed"},
            )
            resolved = await client.post(
                f"/api/v1/alerts/{alert_id}/resolve",
                json={"actor_reference": "district-admin", "note": "Risk subsided"},
            )

            assert acknowledged.status_code == 200
            assert acknowledged.json()["status"] == "ACKNOWLEDGED"
            assert acknowledged.json()["idempotent"] is False
            assert repeated.status_code == 200
            assert repeated.json()["idempotent"] is True
            assert repeated.json()["event_id"] is None
            assert verified.json()["status"] == "VERIFIED"
            assert resolved.json()["status"] == "RESOLVED"

            detail = await client.get(f"/api/v1/alerts/{alert_id}")
            assert detail.status_code == 200
            assert detail.json()["status"] == "RESOLVED"
            assert [event["event_type"] for event in detail.json()["events"]] == [
                "CREATED",
                "ACKNOWLEDGED",
                "VERIFIED",
                "RESOLVED",
            ]
            assert detail.json()["events"][1]["actor_reference"] == "district-admin"

            next_prediction = await client.post(
                "/api/v1/predict",
                json={"cell_code": cell_code, "rainfall_mm": 120},
            )
            assert next_prediction.status_code == 201
            assert next_prediction.json()["alert"]["action"] == "CREATED"
            assert next_prediction.json()["alert"]["alert_id"] != str(alert_id)
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM risk_cells WHERE id = :cell_id"),
                {"cell_id": cell_id},
            )
        await engine.dispose()


def test_alert_lifecycle_is_audited_and_reopens_after_resolution() -> None:
    asyncio.run(assert_alert_lifecycle_api())
