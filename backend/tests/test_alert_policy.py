import pytest

from app.schemas.alert import AlertSeverity
from app.schemas.prediction import RiskLevel
from app.services.alert_policy import AlertPolicy


@pytest.mark.parametrize("risk_level", [RiskLevel.LOW, RiskLevel.MEDIUM])
def test_alert_policy_ignores_non_high_risk(risk_level: RiskLevel) -> None:
    assert AlertPolicy().severity_for(risk_level) is None


@pytest.mark.parametrize(
    ("risk_level", "expected"),
    [
        (RiskLevel.HIGH, AlertSeverity.HIGH),
        (RiskLevel.CRITICAL, AlertSeverity.CRITICAL),
    ],
)
def test_alert_policy_maps_high_risk_to_alert_severity(
    risk_level: RiskLevel,
    expected: AlertSeverity,
) -> None:
    assert AlertPolicy().severity_for(risk_level) == expected
