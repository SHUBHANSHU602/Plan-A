from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertEvent
from app.models.risk import RiskCell
from app.schemas.alert import AlertStatus

OPEN_ALERT_STATUSES = (
    AlertStatus.ACTIVE.value,
    AlertStatus.ACKNOWLEDGED.value,
    AlertStatus.VERIFIED.value,
)


@dataclass(frozen=True)
class AlertRecord:
    alert: Alert
    cell_code: str


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_cell(self, cell_id: UUID) -> None:
        # Transaction-scoped advisory locking closes the concurrent SELECT/INSERT race.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:cell_id AS text), 0))"),
            {"cell_id": str(cell_id)},
        )

    async def get_open_for_update(self, cell_id: UUID) -> Alert | None:
        statement = (
            select(Alert)
            .where(Alert.cell_id == cell_id, Alert.status.in_(OPEN_ALERT_STATUSES))
            .with_for_update()
        )
        return await self._session.scalar(statement)

    async def save(self, alert: Alert) -> Alert:
        self._session.add(alert)
        await self._session.flush()
        await self._session.refresh(alert)
        return alert

    async def get_for_update(self, alert_id: UUID) -> Alert | None:
        statement = select(Alert).where(Alert.id == alert_id).with_for_update()
        return await self._session.scalar(statement)

    async def get_record(self, alert_id: UUID) -> AlertRecord | None:
        statement = (
            select(Alert, RiskCell.cell_code)
            .join(RiskCell, Alert.cell_id == RiskCell.id)
            .where(Alert.id == alert_id)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return AlertRecord(alert=row.Alert, cell_code=row.cell_code)

    async def list_records(
        self,
        *,
        status: str | None,
        severity: str | None,
        cell_code: str | None,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[AlertRecord]:
        statement = select(Alert, RiskCell.cell_code).join(RiskCell, Alert.cell_id == RiskCell.id)
        if status is not None:
            statement = statement.where(Alert.status == status)
        if severity is not None:
            statement = statement.where(Alert.severity == severity)
        if cell_code is not None:
            statement = statement.where(RiskCell.cell_code == cell_code)
        if cursor is not None:
            created_at, alert_id = cursor
            statement = statement.where(
                or_(
                    Alert.created_at < created_at,
                    and_(Alert.created_at == created_at, Alert.id < alert_id),
                )
            )

        statement = statement.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
        rows = (await self._session.execute(statement)).all()
        return [AlertRecord(alert=row.Alert, cell_code=row.cell_code) for row in rows]


class AlertEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: AlertEvent) -> AlertEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_for_alert(self, alert_id: UUID) -> list[AlertEvent]:
        statement = (
            select(AlertEvent)
            .where(AlertEvent.alert_id == alert_id)
            .order_by(AlertEvent.created_at, AlertEvent.id)
        )
        return list(await self._session.scalars(statement))
