from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Plan-A API"
    app_version: str = "0.2.0"
    database_url: str = "postgresql+psycopg://plan_a:plan_a_local@localhost:5432/plan_a"
    database_echo: bool = False
    model_provider: Literal["mock", "artifact"] = "mock"
    model_artifact_path: Path = (
        Path(__file__).resolve().parents[1] / "model_artifacts" / "landslide_model.joblib"
    )
    model_manifest_path: Path = (
        Path(__file__).resolve().parents[1] / "model_artifacts" / "model_manifest.json"
    )
    risk_medium_threshold: float = 0.40
    risk_high_threshold: float = 0.65
    risk_critical_threshold: float = 0.80
    alert_exposure_radius_m: float = Field(default=2_000, gt=0, le=50_000)
    alert_dedup_cooldown_minutes: int = Field(default=30, ge=1, le=1_440)
    fcm_enabled: bool = False
    fcm_project_id: str | None = None
    fcm_max_attempts: int = Field(default=5, ge=1, le=10)
    fcm_retry_base_seconds: int = Field(default=30, ge=1, le=3_600)
    fcm_request_timeout_seconds: int = Field(default=15, ge=1, le=120)
    scheduler_enabled: bool = True
    rainfall_processing_interval_seconds: int = Field(default=60, ge=5, le=3_600)
    notification_retry_interval_seconds: int = Field(default=30, ge=5, le=3_600)
    scheduler_batch_size: int = Field(default=100, ge=1, le=1_000)
    rainfall_processing_max_attempts: int = Field(default=3, ge=1, le=10)
    rainfall_processing_retry_seconds: int = Field(default=30, ge=1, le=3_600)
    rainfall_processing_claim_timeout_seconds: int = Field(default=300, ge=30, le=3_600)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_risk_thresholds(self) -> "Settings":
        thresholds = (
            self.risk_medium_threshold,
            self.risk_high_threshold,
            self.risk_critical_threshold,
        )
        if not 0 < thresholds[0] < thresholds[1] < thresholds[2] < 1:
            raise ValueError(
                "risk thresholds must be ordered between zero and one: medium < high < critical"
            )
        if self.fcm_enabled and not self.fcm_project_id:
            raise ValueError("fcm_project_id is required when FCM is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
