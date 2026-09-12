from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PredictionRequest(BaseModel):
    cell_code: str = Field(min_length=1, max_length=64)
    rainfall_mm: float = Field(ge=0)


class ModelFeatures(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float
    slope_deg: float = Field(ge=0, le=90)
    aspect_deg: float = Field(ge=0, lt=360)
    rainfall_mm: float = Field(ge=0)


class ModelPrediction(BaseModel):
    probability: float = Field(ge=0, le=1)
    predicted_class: Literal[0, 1]
    drivers: list[str] = Field(default_factory=list)


class PredictionResponse(BaseModel):
    snapshot_id: UUID
    cell_id: UUID
    cell_code: str
    probability: float = Field(ge=0, le=1)
    predicted_class: Literal[0, 1]
    risk_level: RiskLevel
    rainfall_mm: float = Field(ge=0)
    drivers: list[str]
    recorded_at: datetime
