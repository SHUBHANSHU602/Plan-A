from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "plan-a-api"}


def test_readiness_check_executes_database_probe() -> None:
    class StubSession:
        called = False

        async def execute(self, _statement: object) -> None:
            self.called = True

    session = StubSession()

    async def override_session():
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "available"}
    assert session.called is True
