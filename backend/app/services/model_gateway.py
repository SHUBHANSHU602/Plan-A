from typing import Protocol

from app.schemas.prediction import ModelFeatures, ModelPrediction


class ModelGateway(Protocol):
    async def predict(self, features: ModelFeatures) -> ModelPrediction: ...


class MockModelGateway:
    """Temporary adapter used until the trained model artifact is integrated."""

    async def predict(self, features: ModelFeatures) -> ModelPrediction:
        drivers: list[str] = []
        if features.rainfall_mm >= 100:
            drivers.append("High rainfall")
        if features.slope_deg >= 30:
            drivers.append("Steep slope")

        return ModelPrediction(
            probability=0.87,
            predicted_class=1,
            drivers=drivers,
        )
