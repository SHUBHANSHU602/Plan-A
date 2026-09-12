from app.schemas.alert import AlertSeverity
from app.schemas.prediction import RiskLevel


class AlertPolicy:
    """Configurable thresholds are classified upstream; alerts begin at HIGH."""

    _severity_by_level = {
        RiskLevel.HIGH: AlertSeverity.HIGH,
        RiskLevel.CRITICAL: AlertSeverity.CRITICAL,
    }

    def severity_for(self, risk_level: RiskLevel) -> AlertSeverity | None:
        return self._severity_by_level.get(risk_level)
