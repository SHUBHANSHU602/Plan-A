from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AssetType(StrEnum):
    VILLAGE = "VILLAGE"
    ROAD = "ROAD"
    HOSPITAL = "HOSPITAL"
    SCHOOL = "SCHOOL"
    BRIDGE = "BRIDGE"
    RAILWAY = "RAILWAY"


class ExposedAsset(BaseModel):
    id: UUID
    asset_code: str
    name: str
    asset_type: AssetType
    criticality: int = Field(ge=1, le=5)
    distance_m: float = Field(ge=0)
    geometry: dict[str, Any]
    properties: dict[str, Any]


class ExposureResponse(BaseModel):
    cell_id: UUID
    cell_code: str
    radius_m: float = Field(gt=0, le=50_000)
    total_assets: int = Field(ge=0)
    counts: dict[AssetType, int]
    assets: list[ExposedAsset]
