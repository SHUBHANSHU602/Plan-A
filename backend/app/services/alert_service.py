from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.models.alert import Alert, AlertEvent
from app.models.risk import RiskSnapshot
from app.repositories.alert import AlertEventRepository, AlertRepository
from app.repositories.exposure import AssetRepository
from app.schemas.alert import AlertAction, AlertEvaluation, AlertSeverity
from app.schemas.exposure import AssetType
from app.schemas.prediction import RiskLevel
from app.services.alert_policy import AlertPolicy

SEVERITY_RANK = {
    AlertSeverity.HIGH: 1,
    AlertSeverity.CRITICAL: 2,
}


def utc_now() -> datetime:
    return datetime.now(UTC)


class AlertService:
    def __init__(
        self,
        repository: AlertRepository,
        event_repository: AlertEventRepository,
        asset_repository: AssetRepository,
        policy: AlertPolicy,
        exposure_radius_m: float,
        dedup_cooldown: timedelta,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._event_repository = event_repository
        self._asset_repository = asset_repository
        self._policy = policy
        self._exposure_radius_m = exposure_radius_m
        self._dedup_cooldown = dedup_cooldown
        self._clock = clock

    async def evaluate(
        self,
        snapshot: RiskSnapshot,
        cell_code: str,
    ) -> AlertEvaluation | None:
        severity = self._policy.severity_for(RiskLevel(snapshot.risk_level))
        if severity is None:
            return None

        records = await self._asset_repository.find_within_radius(
            snapshot.cell_id,
            self._exposure_radius_m,
        )
        exposure = self._summarize_exposure(records)
        now = self._clock()

        await self._repository.lock_cell(snapshot.cell_id)
        existing = await self._repository.get_open_for_update(snapshot.cell_id)

        if existing is None:
            alert = Alert(
                cell_id=snapshot.cell_id,
                latest_snapshot_id=snapshot.id,
                severity=severity.value,
                status="ACTIVE",
                title=self._title(severity),
                message=self._message(cell_code, severity, exposure["total_assets"]),
                current_probability=snapshot.probability,
                peak_probability=snapshot.probability,
                drivers=snapshot.drivers,
                exposure=exposure,
                occurrence_count=1,
                first_seen_at=now,
                last_seen_at=now,
                last_emitted_at=now,
            )
            action = AlertAction.CREATED
        else:
            alert = existing
            previous_severity = AlertSeverity(alert.severity)
            escalated = SEVERITY_RANK[severity] > SEVERITY_RANK[previous_severity]
            cooldown_elapsed = now - alert.last_emitted_at >= self._dedup_cooldown

            if escalated:
                action = AlertAction.ESCALATED
            elif cooldown_elapsed:
                action = AlertAction.REFRESHED
            else:
                action = AlertAction.SUPPRESSED

            alert.latest_snapshot_id = snapshot.id
            alert.severity = severity.value
            alert.title = self._title(severity)
            alert.message = self._message(cell_code, severity, exposure["total_assets"])
            alert.current_probability = snapshot.probability
            alert.peak_probability = max(alert.peak_probability, snapshot.probability)
            alert.drivers = snapshot.drivers
            alert.exposure = exposure
            alert.occurrence_count += 1
            alert.last_seen_at = now
            if action != AlertAction.SUPPRESSED:
                alert.last_emitted_at = now

        await self._repository.save(alert)
        if action != AlertAction.SUPPRESSED:
            await self._event_repository.add(
                AlertEvent(
                    alert_id=alert.id,
                    event_type=action.value,
                    from_status=alert.status,
                    to_status=alert.status,
                    actor_type="SYSTEM",
                    actor_reference="alert-engine",
                    note=None,
                    created_at=now,
                )
            )
        return AlertEvaluation(
            alert_id=alert.id,
            action=action,
            severity=severity,
            occurrence_count=alert.occurrence_count,
        )

    def _summarize_exposure(self, records) -> dict:
        counts = {asset_type.value: 0 for asset_type in AssetType}
        critical_assets = 0
        for record in records:
            counts[record.asset.asset_type] += 1
            if record.asset.criticality >= 4:
                critical_assets += 1

        return {
            "radius_m": self._exposure_radius_m,
            "total_assets": len(records),
            "critical_assets": critical_assets,
            "counts": counts,
        }

    @staticmethod
    def _title(severity: AlertSeverity) -> str:
        return f"{severity.value.title()} Landslide Risk"

    @staticmethod
    def _message(cell_code: str, severity: AlertSeverity, total_assets: int) -> str:
        return (
            f"{severity.value.title()} model-estimated landslide risk detected for "
            f"cell {cell_code}; {total_assets} nearby assets identified."
        )
