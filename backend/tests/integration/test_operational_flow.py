import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api import dependencies
from app.db.session import engine
from app.main import app
from app.scheduler.jobs import process_rainfall_observations

pytestmark = pytest.mark.integration

if os.getenv("RUN_DATABASE_TESTS") != "1":
    pytest.skip("database integration tests are disabled", allow_module_level=True)

cell_id = uuid4()
cell_code = f"operational-cell-{cell_id}"
registration_id = f"operational-installation-{uuid4()}"


class FakePushClient:
    def __init__(self) -> None:
        self.events = []

    async def send(self, installation_id, event):
        assert installation_id == registration_id
        self.events.append(event)
        return f"projects/test/messages/{event.event_id}"


async def seed_cell() -> None:
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
                        'POLYGON((82.00 23.00, 82.02 23.00, 82.02 23.02, '
                        '82.00 23.02, 82.00 23.00))',
                        4326
                    ),
                    213, 50.76, 22.93
                )
                """
            ),
            {"id": cell_id, "cell_code": cell_code},
        )


async def assert_operational_flow() -> None:
    original_client = dependencies.firebase_client
    fake_client = FakePushClient()
    subscription_id = None
    dependencies.firebase_client = fake_client
    try:
        await seed_cell()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            subscription = await client.post(
                "/api/v1/notifications/subscriptions",
                json={
                    "registration_id": registration_id,
                    "platform": "WEB",
                    "subscriber_reference": "operational-dashboard",
                },
            )
            assert subscription.status_code == 201
            subscription_id = UUID(subscription.json()["id"])

            baseline = await client.post(
                "/api/v1/predict",
                json={"cell_code": cell_code, "rainfall_mm": 30},
            )
            assert baseline.status_code == 201
            assert baseline.json()["risk_level"] == "MEDIUM"
            assert baseline.json()["alert"] is None

            simulation = await client.post(
                "/api/v1/simulation/rainfall",
                json={"cell_code": cell_code, "rainfall_multiplier": 3},
            )
            assert simulation.status_code == 201
            simulation_payload = simulation.json()
            assert simulation_payload["baseline_rainfall_mm"] == 30
            assert simulation_payload["simulated_rainfall_mm"] == 90
            assert simulation_payload["prediction"]["risk_level"] == "HIGH"
            assert simulation_payload["prediction"]["alert"]["action"] == "CREATED"

            observed_at = datetime.now(UTC).isoformat()
            observation = await client.post(
                "/api/v1/rainfall/observations",
                json={
                    "cell_code": cell_code,
                    "source": "IMD-DEMO",
                    "source_event_id": f"rain-{cell_id}",
                    "rainfall_mm": 150,
                    "observed_at": observed_at,
                },
            )
            duplicate = await client.post(
                "/api/v1/rainfall/observations",
                json={
                    "cell_code": cell_code,
                    "source": "IMD-DEMO",
                    "source_event_id": f"rain-{cell_id}",
                    "rainfall_mm": 150,
                    "observed_at": observed_at,
                },
            )
            assert observation.status_code == 202
            assert duplicate.json()["id"] == observation.json()["id"]

            await process_rainfall_observations()

            alert_id = simulation_payload["prediction"]["alert"]["alert_id"]
            deliveries = await client.get(
                "/api/v1/notifications/deliveries",
                params={"alert_id": alert_id},
            )

        async with engine.connect() as connection:
            observation_status = await connection.scalar(
                text("SELECT status FROM rainfall_observations WHERE id = :id"),
                {"id": UUID(observation.json()["id"])},
            )
            simulation_status = await connection.scalar(
                text("SELECT status FROM simulation_runs WHERE id = :id"),
                {"id": UUID(simulation_payload["run_id"])},
            )

        assert observation_status == "PROCESSED"
        assert simulation_status == "COMPLETED"
        assert [event.event_type.value for event in fake_client.events] == [
            "CREATED",
            "ESCALATED",
        ]
        assert [item["status"] for item in deliveries.json()["items"]] == ["SENT", "SENT"]
    finally:
        dependencies.firebase_client = original_client
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM risk_cells WHERE id = :cell_id"),
                {"cell_id": cell_id},
            )
            if subscription_id is not None:
                await connection.execute(
                    text("DELETE FROM notification_subscriptions WHERE id = :id"),
                    {"id": subscription_id},
                )
        await engine.dispose()


def test_rainfall_change_creates_alert_and_notification() -> None:
    asyncio.run(assert_operational_flow())
