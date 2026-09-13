import pytest

from app.schemas.prediction import RiskLevel
from app.services.risk_classifier import RiskClassifier, RiskThresholds

classifier = RiskClassifier(RiskThresholds(medium=0.40, high=0.65, critical=0.80))


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.0, RiskLevel.LOW),
        (0.3999, RiskLevel.LOW),
        (0.40, RiskLevel.MEDIUM),
        (0.6499, RiskLevel.MEDIUM),
        (0.65, RiskLevel.HIGH),
        (0.7999, RiskLevel.HIGH),
        (0.80, RiskLevel.CRITICAL),
        (1.0, RiskLevel.CRITICAL),
    ],
)
def test_classifier_boundaries(probability: float, expected: RiskLevel) -> None:
    assert classifier.classify(probability) is expected
