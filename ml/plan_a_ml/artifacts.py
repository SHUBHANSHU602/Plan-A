import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from plan_a_ml.pipeline import FEATURE_COLUMNS, TrainingResult, predict_probability

DRY_SCENARIO = {
    "Elevation_m": 250.0,
    "Slope_deg": 10.0,
    "Aspect_deg": 90.0,
    "Rainfall_mm": 5.0,
    "Rainfall_7day_antecedent_mm": 12.0,
    "Rainfall_Event_ERA5_mm": 5.0,
    "Soil_Clay_pct": 22.0,
    "Soil_Sand_pct": 48.0,
}
MONSOON_SCENARIO = {
    "Elevation_m": 850.0,
    "Slope_deg": 42.0,
    "Aspect_deg": 145.0,
    "Rainfall_mm": 185.0,
    "Rainfall_7day_antecedent_mm": 240.0,
    "Rainfall_Event_ERA5_mm": 135.0,
    "Soil_Clay_pct": 35.5,
    "Soil_Sand_pct": 28.0,
}


def dataset_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_bundle(result: TrainingResult, dataset_path: Path, output_dir: Path) -> dict[str, object]:
    dry_probability = predict_probability(result.model, DRY_SCENARIO)
    monsoon_probability = predict_probability(result.model, MONSOON_SCENARIO)
    if dry_probability >= monsoon_probability:
        raise ValueError(
            "scenario sanity check failed: dry probability must be below monsoon probability"
        )
    if result.split["group_overlap"]:
        raise ValueError("spatial train/test groups overlap")

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "landslide_model.joblib"
    manifest_path = output_dir / "model_manifest.json"
    joblib.dump(result.model, model_path)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "model_type": type(result.model).__name__,
        "feature_names": list(FEATURE_COLUMNS),
        "model_parameters": {
            key: result.model.get_params()[key]
            for key in (
                "n_estimators",
                "max_depth",
                "min_samples_leaf",
                "class_weight",
                "random_state",
            )
        },
        "metrics": result.metrics,
        "feature_importances": result.feature_importances,
        "feature_stats": result.feature_stats,
        "split": result.split,
        "dataset": {
            "filename": dataset_path.name,
            "sha256": dataset_sha256(dataset_path),
        },
        "demo_scenarios": {
            "dry_probability": dry_probability,
            "monsoon_probability": monsoon_probability,
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "explanation_method": "transparent_threshold_heuristic_not_shap",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
