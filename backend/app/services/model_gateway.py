from typing import Protocol

from app.schemas.prediction import ModelFeatures, ModelPrediction


class ModelGateway(Protocol):
    async def predict(self, features: ModelFeatures) -> ModelPrediction: ...


class MockModelGateway:
    """Deterministic demo adapter until the trained model artifact is integrated.

    The coefficients are operational demo values, not scientific thresholds.
    """

    async def predict(self, features: ModelFeatures) -> ModelPrediction:
        drivers: list[str] = []
        if features.rainfall_mm >= 100:
            drivers.append("High rainfall")
        if features.slope_deg >= 30:
            drivers.append("Steep slope")

        probability = round(
            min(
                0.99,
                max(
                    0.01,
                    0.24 + (0.0035 * features.rainfall_mm) + (0.00446 * features.slope_deg),
                ),
            ),
            2,
        )

        return ModelPrediction(
            probability=probability,
            predicted_class=int(probability >= 0.5),
            drivers=drivers,
        )
