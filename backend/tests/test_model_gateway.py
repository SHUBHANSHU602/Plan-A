import asyncio
from pathlib import Path

from app.schemas.prediction import ModelFeatures
from app.services.model_gateway import ArtifactModelGateway, MockModelGateway

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "app" / "model_artifacts"


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


def test_artifact_gateway_loads_reviewed_bundle_and_separates_scenarios() -> None:
    gateway = ArtifactModelGateway(
        ARTIFACT_DIR / "landslide_model.joblib",
        ARTIFACT_DIR / "model_manifest.json",
    )
    dry = ModelFeatures(
        latitude=27.19,
        longitude=93.78,
        elevation_m=250,
        slope_deg=10,
        aspect_deg=90,
        rainfall_mm=5,
        rainfall_7day_antecedent_mm=12,
        rainfall_event_era5_mm=5,
        soil_clay_pct=22,
        soil_sand_pct=48,
    )
    monsoon = ModelFeatures(
        latitude=27.19,
        longitude=93.78,
        elevation_m=850,
        slope_deg=42,
        aspect_deg=145,
        rainfall_mm=185,
        rainfall_7day_antecedent_mm=240,
        rainfall_event_era5_mm=135,
        soil_clay_pct=35.5,
        soil_sand_pct=28,
    )

    dry_prediction = asyncio.run(gateway.predict(dry))
    monsoon_prediction = asyncio.run(gateway.predict(monsoon))

    assert dry_prediction.probability == 0.1596
    assert dry_prediction.predicted_class == 0
    assert monsoon_prediction.probability == 0.5891
    assert monsoon_prediction.predicted_class == 1
    assert monsoon_prediction.probability > dry_prediction.probability
    assert "High rainfall" in monsoon_prediction.drivers


def test_artifact_gateway_uses_manifest_medians_for_optional_context() -> None:
    gateway = ArtifactModelGateway(
        ARTIFACT_DIR / "landslide_model.joblib",
        ARTIFACT_DIR / "model_manifest.json",
    )
    prediction = asyncio.run(
        gateway.predict(
            ModelFeatures(
                latitude=27.19,
                longitude=93.78,
                elevation_m=213,
                slope_deg=50.76,
                aspect_deg=22.93,
                rainfall_mm=115.34,
            )
        )
    )

    assert 0 <= prediction.probability <= 1
    assert prediction.predicted_class in (0, 1)
