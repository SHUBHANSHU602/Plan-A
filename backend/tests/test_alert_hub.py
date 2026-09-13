import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.realtime.alert_hub import AlertWebSocketHub
from app.schemas.alert import AlertEventType
from app.schemas.notification import NotificationEvent


class StubWebSocket:
    def __init__(self, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.fail_send:
            raise RuntimeError("connection closed")
        self.messages.append(message)


async def assert_broadcast_delivers_and_removes_dead_connections() -> None:
    hub = AlertWebSocketHub()
    healthy = StubWebSocket()
    failing = StubWebSocket(fail_send=True)
    await hub.connect(healthy)
    await hub.connect(failing)
    event = NotificationEvent(
        event_id=uuid4(),
        alert_id=uuid4(),
        event_type=AlertEventType.CREATED,
        occurred_at=datetime.now(UTC),
        payload={"cell_code": "A17"},
    )

    delivered = await hub.broadcast(event)

    assert delivered == 1
    assert hub.connection_count == 1
    assert healthy.messages[0]["type"] == "alert.event"
    assert healthy.messages[0]["data"]["alert_id"] == str(event.alert_id)


def test_broadcast_delivers_and_removes_dead_connections() -> None:
    asyncio.run(assert_broadcast_delivers_and_removes_dead_connections())
