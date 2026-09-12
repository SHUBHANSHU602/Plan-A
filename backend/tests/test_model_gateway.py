import asyncio

from app.schemas.prediction import ModelFeatures
from app.services.model_gateway import MockModelGateway


def test_mock_gateway_obeys_the_agreed_model_contract() -> None:
    features = ModelFeatures(
        latitude=27.19343,
        longitude=93.78098,
        elevation_m=213,
        slope_deg=50.76,
        aspect_deg=22.93,
        rainfall_mm=115.34,
    )

    prediction = asyncio.run(MockModelGateway().predict(features))

    assert prediction.probability == 0.87
    assert prediction.predicted_class == 1
    assert prediction.drivers == ["High rainfall", "Steep slope"]
