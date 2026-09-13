import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.realtime.alert_hub import alert_websocket_hub
from app.schemas.notification import WebSocketControlMessage

router = APIRouter(tags=["live alerts"])


@router.websocket("/ws/alerts")
async def stream_alerts(websocket: WebSocket) -> None:
    connection = await alert_websocket_hub.connect(websocket)
    await alert_websocket_hub.send_json(
        connection,
        {"type": "connection.ready", "version": "1"},
    )
    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                message = WebSocketControlMessage.model_validate(json.loads(raw_message))
            except (json.JSONDecodeError, ValidationError):
                await alert_websocket_hub.send_json(
                    connection,
                    {"type": "error", "detail": "invalid control message"},
                )
                continue

            if message.type == "ping":
                await alert_websocket_hub.send_json(connection, {"type": "pong"})
            else:
                await alert_websocket_hub.send_json(
                    connection,
                    {"type": "error", "detail": "unsupported control message"},
                )
    except WebSocketDisconnect:
        pass
    finally:
        await alert_websocket_hub.disconnect(connection)
