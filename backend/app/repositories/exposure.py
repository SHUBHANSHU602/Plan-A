import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.risk import RiskCell


@dataclass(frozen=True)
class ExposedAssetRecord:
    asset: Asset
    distance_m: float
    geometry: dict[str, Any]


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_within_radius(
        self,
        cell_id: UUID,
        radius_m: float,
    ) -> list[ExposedAssetRecord]:
        cell_geometry = select(RiskCell.geometry).where(RiskCell.id == cell_id).scalar_subquery()
        asset_geography = Asset.geometry
        cell_geography = cast(cell_geometry, Geography(srid=4326))
        distance_m = func.ST_Distance(asset_geography, cell_geography)

        statement = (
            select(
                Asset,
                distance_m.label("distance_m"),
                func.ST_AsGeoJSON(Asset.geometry).label("geometry_json"),
            )
            .where(func.ST_DWithin(asset_geography, cell_geography, radius_m))
            .order_by(distance_m, Asset.asset_code)
        )
        rows = (await self._session.execute(statement)).all()

        return [
            ExposedAssetRecord(
                asset=row.Asset,
                distance_m=float(row.distance_m),
                geometry=json.loads(row.geometry_json),
            )
            for row in rows
        ]
