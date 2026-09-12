from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Plan-A API"
    app_version: str = "0.2.0"
    database_url: str = "postgresql+psycopg://plan_a:plan_a_local@localhost:5432/plan_a"
    database_echo: bool = False
    risk_medium_threshold: float = 0.40
    risk_high_threshold: float = 0.65
    risk_critical_threshold: float = 0.80

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
