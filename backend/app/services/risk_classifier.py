from dataclasses import dataclass

from app.schemas.prediction import RiskLevel


@dataclass(frozen=True)
class RiskThresholds:
    medium: float
    high: float
    critical: float


class RiskClassifier:
    def __init__(self, thresholds: RiskThresholds) -> None:
        self._thresholds = thresholds

    def classify(self, probability: float) -> RiskLevel:
        if probability >= self._thresholds.critical:
            return RiskLevel.CRITICAL
        if probability >= self._thresholds.high:
            return RiskLevel.HIGH
        if probability >= self._thresholds.medium:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
