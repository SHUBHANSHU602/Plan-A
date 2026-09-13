from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from plan_a_ml.artifacts import DRY_SCENARIO, MONSOON_SCENARIO, save_bundle
from plan_a_ml.data import FEATURE_BOUNDS, clean_dataset
from plan_a_ml.pipeline import FEATURE_COLUMNS, predict_probability, train_and_evaluate


def synthetic_frame(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for group in range(24):
        latitude = 24.0 + (group // 6) * 0.4
        longitude = 91.0 + (group % 6) * 0.4
        for index in range(16):
            high = index % 2 == 1
            rows.append(
                {
                    "Latitude": latitude + rng.normal(0, 0.02),
                    "Longitude": longitude + rng.normal(0, 0.02),
                    "Elevation_m": rng.normal(900 if high else 300, 70),
                    "Slope_deg": rng.normal(40 if high else 9, 2),
                    "Aspect_deg": rng.uniform(0, 359),
                    "Rainfall_mm": rng.normal(180 if high else 8, 4),
                    "Rainfall_7day_antecedent_mm": rng.normal(230 if high else 14, 8),
                    "Rainfall_Event_ERA5_mm": rng.normal(120 if high else 6, 3),
                    "Soil_Clay_pct": rng.normal(36 if high else 21, 2),
                    "Soil_Sand_pct": rng.normal(28 if high else 50, 3),
                    "Landslide_Label": int(high),
                }
            )
    frame = pd.DataFrame(rows)
    for feature, (minimum, maximum) in FEATURE_BOUNDS.items():
        frame[feature] = frame[feature].clip(minimum, maximum)
    return frame


def test_cleaning_rejects_invalid_rows_and_requires_both_classes() -> None:
    frame = synthetic_frame()
    invalid = frame.iloc[[0]].copy()
    invalid["Slope_deg"] = 120
    duplicate = frame.iloc[[1]].copy()
    cleaned = clean_dataset(
        pd.concat([frame, invalid, duplicate], ignore_index=True), FEATURE_COLUMNS
    )
    assert cleaned.dropped_rows == 2
    assert set(cleaned.class_counts) == {0, 1}
    assert cleaned.duplicate_rows == 1

    with pytest.raises(ValueError, match="both"):
        clean_dataset(frame.loc[frame["Landslide_Label"] == 1], FEATURE_COLUMNS)


def test_training_has_disjoint_spatial_holdout_and_sensible_scenarios(tmp_path: Path) -> None:
    dataset_path = tmp_path / "fixture.csv"
    frame = synthetic_frame()
    frame.to_csv(dataset_path, index=False)
    result = train_and_evaluate(clean_dataset(frame, FEATURE_COLUMNS))

    assert result.split["strategy"] == "spatial_group_holdout"
    assert result.split["group_overlap"] == []
    assert result.metrics["roc_auc"] > 0.9
    assert result.metrics["pr_auc"] > 0.9
    assert predict_probability(result.model, DRY_SCENARIO) < predict_probability(
        result.model, MONSOON_SCENARIO
    )

    manifest = save_bundle(result, dataset_path, tmp_path / "artifacts")
    assert manifest["model_parameters"]["n_estimators"] == 50
    assert manifest["model_parameters"]["max_depth"] == 8
    assert manifest["model_parameters"]["class_weight"] == "balanced"
    assert len(manifest["dataset"]["sha256"]) == 64
    assert len(manifest["model"]["sha256"]) == 64


def test_prediction_rejects_missing_features() -> None:
    result = train_and_evaluate(clean_dataset(synthetic_frame(), FEATURE_COLUMNS))
    with pytest.raises(ValueError, match="missing features"):
        predict_probability(result.model, {"Rainfall_mm": 100})
