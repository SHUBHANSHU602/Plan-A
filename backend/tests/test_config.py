from app.core.config import Settings
from app.main import create_app


def test_settings_read_database_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@db/test")
    monkeypatch.setenv("DATABASE_ECHO", "true")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://test:test@db/test"
    assert settings.database_echo is True


def test_application_metadata_comes_from_settings() -> None:
    application = create_app()

    assert application.title == "Plan-A API"
    assert application.version == "0.2.0"
