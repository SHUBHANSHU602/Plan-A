from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk import RiskCell, RiskSnapshot


@dataclass(frozen=True)
class RiskCellFeatureSet:
    cell: RiskCell
    latitude: float
    longitude: float


class RiskCellRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, cell_code: str) -> RiskCell | None:
        return await self._session.scalar(select(RiskCell).where(RiskCell.cell_code == cell_code))

    async def get_by_id(self, cell_id) -> RiskCell | None:
        return await self._session.get(RiskCell, cell_id)

    async def get_feature_set(self, cell_code: str) -> RiskCellFeatureSet | None:
        centroid = func.ST_Centroid(RiskCell.geometry)
        statement = select(
            RiskCell,
            func.ST_Y(centroid).label("latitude"),
            func.ST_X(centroid).label("longitude"),
        ).where(RiskCell.cell_code == cell_code)
        row = (await self._session.execute(statement)).one_or_none()

        if row is None:
            return None

        cell, latitude, longitude = row
        return RiskCellFeatureSet(
            cell=cell,
            latitude=float(latitude),
            longitude=float(longitude),
        )


class RiskSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, snapshot: RiskSnapshot) -> RiskSnapshot:
        self._session.add(snapshot)
        try:
            await self._session.flush()
            await self._session.refresh(snapshot)
        except Exception:
            await self._session.rollback()
            raise
        return snapshot

    async def get_latest_for_cell(self, cell_id) -> RiskSnapshot | None:
        statement = (
            select(RiskSnapshot)
            .where(RiskSnapshot.cell_id == cell_id)
            .order_by(RiskSnapshot.recorded_at.desc(), RiskSnapshot.id.desc())
            .limit(1)
        )
        return await self._session.scalar(statement)
