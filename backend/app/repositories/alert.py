from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.schemas.alert import AlertStatus

OPEN_ALERT_STATUSES = (
    AlertStatus.ACTIVE.value,
    AlertStatus.ACKNOWLEDGED.value,
    AlertStatus.VERIFIED.value,
)


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
        return alert
