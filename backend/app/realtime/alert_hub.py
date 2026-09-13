import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.schemas.notification import NotificationEvent


@dataclass(eq=False)
class AlertConnection:
    websocket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AlertWebSocketHub:
    def __init__(self) -> None:
        self._connections: set[AlertConnection] = set()
        self._connections_lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> AlertConnection:
        await websocket.accept()
        connection = AlertConnection(websocket)
        async with self._connections_lock:
            self._connections.add(connection)
        return connection

    async def disconnect(self, connection: AlertConnection) -> None:
        async with self._connections_lock:
            self._connections.discard(connection)

    async def send_json(self, connection: AlertConnection, message: dict) -> None:
        async with connection.send_lock:
            await connection.websocket.send_json(message)

    async def broadcast(self, event: NotificationEvent) -> int:
        async with self._connections_lock:
            connections = tuple(self._connections)
        if not connections:
            return 0

        payload = {
            "type": "alert.event",
            "data": event.model_dump(mode="json"),
        }
        results = await asyncio.gather(
            *(self._send_or_disconnect(connection, payload) for connection in connections)
        )
        return sum(results)

    async def _send_or_disconnect(self, connection: AlertConnection, payload: dict) -> int:
        try:
            await self.send_json(connection, payload)
            return 1
        except Exception:
            await self.disconnect(connection)
            return 0


alert_websocket_hub = AlertWebSocketHub()
