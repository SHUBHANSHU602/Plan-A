from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.prediction import PredictionResponse

SourceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
SourceEventId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]


class ObservationStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class RainfallObservationCreate(BaseModel):
    cell_code: str = Field(min_length=1, max_length=64)
    source: SourceName
    source_event_id: SourceEventId
    rainfall_mm: float = Field(ge=0, le=5_000)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def observed_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class RainfallObservationResponse(BaseModel):
    id: UUID
    cell_id: UUID
    cell_code: str
    source: str
    source_event_id: str
    rainfall_mm: float
    observed_at: datetime
    status: ObservationStatus
    attempt_count: int
    next_attempt_at: datetime | None
    processed_snapshot_id: UUID | None
    last_error: str | None
    created_at: datetime


class RainfallSimulationRequest(BaseModel):
    cell_code: str = Field(min_length=1, max_length=64)
    rainfall_multiplier: float = Field(gt=0, le=10)
    baseline_rainfall_mm: float | None = Field(default=None, ge=0, le=5_000)


class RainfallSimulationResponse(BaseModel):
    run_id: UUID
    baseline_snapshot_id: UUID | None
    baseline_rainfall_mm: float
    rainfall_multiplier: float
    simulated_rainfall_mm: float
    prediction: PredictionResponse
