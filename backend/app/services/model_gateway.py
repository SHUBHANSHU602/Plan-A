import hashlib
import json
from pathlib import Path
from typing import Protocol

import joblib
import pandas as pd

from app.schemas.prediction import ModelFeatures, ModelPrediction


class ModelGateway(Protocol):
    async def predict(self, features: ModelFeatures) -> ModelPrediction: ...


class ModelArtifactError(RuntimeError):
    """Raised when the configured model bundle is missing or internally inconsistent."""


class ArtifactModelGateway:
    """Loads the reviewed Random Forest bundle and exposes the backend contract.

    Antecedent-rainfall and soil inputs are optional during the MVP transition. When an
    upstream adapter does not supply them, the reviewed training median from the manifest
    is used. Callers can provide all four values for full eight-feature inference.
    """

    FEATURE_MAPPING = {
        "Elevation_m": "elevation_m",
        "Slope_deg": "slope_deg",
        "Aspect_deg": "aspect_deg",
        "Rainfall_mm": "rainfall_mm",
        "Rainfall_7day_antecedent_mm": "rainfall_7day_antecedent_mm",
        "Rainfall_Event_ERA5_mm": "rainfall_event_era5_mm",
        "Soil_Clay_pct": "soil_clay_pct",
        "Soil_Sand_pct": "soil_sand_pct",
    }

    def __init__(self, model_path: Path, manifest_path: Path) -> None:
        self._model_path = Path(model_path)
        self._manifest_path = Path(manifest_path)
        self._manifest = self._load_manifest()
        self._feature_names = tuple(self._manifest.get("feature_names", []))
        if self._feature_names != tuple(self.FEATURE_MAPPING):
            raise ModelArtifactError("model manifest feature order does not match backend contract")

        expected_hash = self._manifest.get("model", {}).get("sha256")
        if not expected_hash or self._sha256(self._model_path) != expected_hash:
            raise ModelArtifactError("model artifact checksum does not match its manifest")

        self._model = joblib.load(self._model_path)
        model_features = tuple(getattr(self._model, "feature_names_in_", ()))
        if model_features != self._feature_names:
            raise ModelArtifactError("loaded model feature order does not match its manifest")
        if list(getattr(self._model, "classes_", [])) != [0, 1]:
            raise ModelArtifactError("loaded model must expose binary classes [0, 1]")

    @staticmethod
    def _sha256(path: Path) -> str:
        if not path.is_file():
            raise ModelArtifactError(f"model artifact is missing: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_manifest(self) -> dict:
        if not self._manifest_path.is_file():
            raise ModelArtifactError(f"model manifest is missing: {self._manifest_path}")
        try:
            manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelArtifactError("model manifest is not valid JSON") from error
        if manifest.get("schema_version") != 1:
            raise ModelArtifactError("unsupported model manifest schema version")
        return manifest

    def _values(self, features: ModelFeatures) -> tuple[dict[str, float], set[str]]:
        stats = self._manifest["feature_stats"]
        values: dict[str, float] = {}
        defaulted: set[str] = set()
        for artifact_name, api_name in self.FEATURE_MAPPING.items():
            value = getattr(features, api_name)
            if value is None:
                value = stats[artifact_name]["median"]
                defaulted.add(artifact_name)
            values[artifact_name] = float(value)
        return values, defaulted

    def _drivers(
        self,
        values: dict[str, float],
        defaulted: set[str],
        predicted_class: int,
    ) -> list[str]:
        stats = self._manifest["feature_stats"]
        if predicted_class == 0:
            drivers = []
            if values["Rainfall_mm"] <= stats["Rainfall_mm"]["p25"]:
                drivers.append("Low rainfall")
            if values["Slope_deg"] <= stats["Slope_deg"]["p25"]:
                drivers.append("Gentle terrain slope")
            return drivers or ["Lower multi-factor model score"]

        checks = (
            ("Rainfall_mm", "High rainfall"),
            ("Slope_deg", "Steep slope"),
            ("Elevation_m", "High elevation terrain"),
            ("Rainfall_7day_antecedent_mm", "High 7-day antecedent rainfall"),
            ("Soil_Clay_pct", "High clay soil content"),
        )
        drivers = [
            label
            for name, label in checks
            if name not in defaulted and values[name] >= stats[name]["p75"]
        ]
        return drivers or ["Elevated multi-factor model score"]

    async def predict(self, features: ModelFeatures) -> ModelPrediction:
        values, defaulted = self._values(features)
        row = pd.DataFrame(
            [[values[name] for name in self._feature_names]], columns=self._feature_names
        )
        class_index = list(self._model.classes_).index(1)
        probability = float(self._model.predict_proba(row)[0, class_index])
        predicted_class = int(probability >= 0.5)
        return ModelPrediction(
            probability=round(probability, 4),
            predicted_class=predicted_class,
            drivers=self._drivers(values, defaulted, predicted_class),
        )


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
