import base64
import binascii
from datetime import datetime
from uuid import UUID

from app.db.transaction import TransactionManager
from app.models.alert import Alert, AlertEvent
from app.repositories.alert import AlertEventRepository, AlertRecord, AlertRepository
from app.schemas.alert import (
    AlertActorType,
    AlertDetail,
    AlertEventResponse,
    AlertEventType,
    AlertListResponse,
    AlertSeverity,
    AlertStatus,
    AlertSummary,
    AlertTransitionRequest,
    AlertTransitionResponse,
)

EXPECTED_PREVIOUS_STATUS = {
    AlertStatus.ACKNOWLEDGED: AlertStatus.ACTIVE,
    AlertStatus.VERIFIED: AlertStatus.ACKNOWLEDGED,
    AlertStatus.RESOLVED: AlertStatus.VERIFIED,
}


class AlertNotFoundError(Exception):
    def __init__(self, alert_id: UUID) -> None:
        super().__init__(f"alert '{alert_id}' was not found")
        self.alert_id = alert_id


class InvalidAlertTransitionError(Exception):
    def __init__(self, current: AlertStatus, target: AlertStatus) -> None:
        super().__init__(f"cannot transition alert from {current.value} to {target.value}")
        self.current = current
        self.target = target


class InvalidAlertCursorError(Exception):
    pass


class AlertManagementService:
    def __init__(
        self,
        alert_repository: AlertRepository,
        event_repository: AlertEventRepository,
        transaction: TransactionManager,
    ) -> None:
        self._alert_repository = alert_repository
        self._event_repository = event_repository
        self._transaction = transaction

    async def list_alerts(
        self,
        *,
        status: AlertStatus | None,
        severity: AlertSeverity | None,
        cell_code: str | None,
        cursor: str | None,
        limit: int,
    ) -> AlertListResponse:
        decoded_cursor = self._decode_cursor(cursor) if cursor else None
        records = await self._alert_repository.list_records(
            status=status.value if status else None,
            severity=severity.value if severity else None,
            cell_code=cell_code,
            cursor=decoded_cursor,
            limit=limit + 1,
        )
        has_more = len(records) > limit
        page = records[:limit]
        next_cursor = self._encode_cursor(page[-1].alert) if has_more else None
        return AlertListResponse(
            items=[self._to_summary(record) for record in page],
            next_cursor=next_cursor,
        )

    async def get_alert(self, alert_id: UUID) -> AlertDetail:
        record = await self._alert_repository.get_record(alert_id)
        if record is None:
            raise AlertNotFoundError(alert_id)
        events = await self._event_repository.list_for_alert(alert_id)
        return AlertDetail(
            **self._to_summary(record).model_dump(),
            events=[self._to_event_response(event) for event in events],
        )

    async def transition(
        self,
        alert_id: UUID,
        target: AlertStatus,
        request: AlertTransitionRequest,
    ) -> AlertTransitionResponse:
        try:
            alert = await self._alert_repository.get_for_update(alert_id)
            if alert is None:
                raise AlertNotFoundError(alert_id)

            current = AlertStatus(alert.status)
            if current == target:
                await self._transaction.commit()
                return AlertTransitionResponse(
                    alert_id=alert.id,
                    previous_status=current,
                    status=current,
                    idempotent=True,
                    event_id=None,
                    updated_at=alert.updated_at,
                )

            expected_previous = EXPECTED_PREVIOUS_STATUS.get(target)
            if expected_previous is None or expected_previous != current:
                raise InvalidAlertTransitionError(current, target)

            alert.status = target.value
            await self._alert_repository.save(alert)
            event = await self._event_repository.add(
                AlertEvent(
                    alert_id=alert.id,
                    event_type=AlertEventType(target.value).value,
                    from_status=current.value,
                    to_status=target.value,
                    actor_type=AlertActorType.CLIENT.value,
                    actor_reference=request.actor_reference,
                    note=request.note,
                )
            )
            await self._transaction.commit()
            return AlertTransitionResponse(
                alert_id=alert.id,
                previous_status=current,
                status=target,
                idempotent=False,
                event_id=event.id,
                updated_at=alert.updated_at,
            )
        except Exception:
            await self._transaction.rollback()
            raise

    @staticmethod
    def _to_summary(record: AlertRecord) -> AlertSummary:
        alert = record.alert
        return AlertSummary(
            id=alert.id,
            cell_id=alert.cell_id,
            cell_code=record.cell_code,
            severity=AlertSeverity(alert.severity),
            status=AlertStatus(alert.status),
            title=alert.title,
            message=alert.message,
            current_probability=alert.current_probability,
            peak_probability=alert.peak_probability,
            drivers=alert.drivers,
            exposure=alert.exposure,
            occurrence_count=alert.occurrence_count,
            first_seen_at=alert.first_seen_at,
            last_seen_at=alert.last_seen_at,
            last_emitted_at=alert.last_emitted_at,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )

    @staticmethod
    def _to_event_response(event: AlertEvent) -> AlertEventResponse:
        return AlertEventResponse(
            id=event.id,
            event_type=AlertEventType(event.event_type),
            from_status=AlertStatus(event.from_status),
            to_status=AlertStatus(event.to_status),
            actor_type=AlertActorType(event.actor_type),
            actor_reference=event.actor_reference,
            note=event.note,
            created_at=event.created_at,
        )

    @staticmethod
    def _encode_cursor(alert: Alert) -> str:
        payload = f"{alert.created_at.isoformat()}|{alert.id}".encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.urlsafe_b64decode(cursor + padding).decode()
            timestamp, alert_id = decoded.rsplit("|", 1)
            parsed_timestamp = datetime.fromisoformat(timestamp)
            if parsed_timestamp.tzinfo is None:
                raise ValueError("cursor timestamp must include a timezone")
            return parsed_timestamp, UUID(alert_id)
        except (ValueError, UnicodeDecodeError, binascii.Error) as error:
            raise InvalidAlertCursorError("invalid alert cursor") from error
