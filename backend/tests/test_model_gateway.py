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


async def assert_rainfall_changes_demo_risk() -> None:
    gateway = MockModelGateway()
    static = {
        "latitude": 27.19343,
        "longitude": 93.78098,
        "elevation_m": 213,
        "slope_deg": 50.76,
        "aspect_deg": 22.93,
    }

    baseline = await gateway.predict(ModelFeatures(**static, rainfall_mm=30))
    simulated = await gateway.predict(ModelFeatures(**static, rainfall_mm=90))

    assert baseline.probability == 0.57
    assert simulated.probability == 0.78


def test_mock_gateway_responds_to_rainfall_scenarios() -> None:
    asyncio.run(assert_rainfall_changes_demo_risk())
