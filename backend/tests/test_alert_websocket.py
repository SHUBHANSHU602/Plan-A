from fastapi.testclient import TestClient

from app.main import app


def test_alert_websocket_handshake_and_control_messages() -> None:
    with TestClient(app) as client, client.websocket_connect("/ws/alerts") as websocket:
        assert websocket.receive_json() == {"type": "connection.ready", "version": "1"}

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

        websocket.send_text("not-json")
        assert websocket.receive_json() == {
            "type": "error",
            "detail": "invalid control message",
        }

        websocket.send_json({"type": "unknown"})
        assert websocket.receive_json() == {
            "type": "error",
            "detail": "unsupported control message",
        }
