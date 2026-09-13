from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from plan_a_ml.data import TARGET_COLUMN, CleanedDataset, feature_statistics, spatial_groups

FEATURE_COLUMNS = (
    "Elevation_m",
    "Slope_deg",
    "Aspect_deg",
    "Rainfall_mm",
    "Rainfall_7day_antecedent_mm",
    "Rainfall_Event_ERA5_mm",
    "Soil_Clay_pct",
    "Soil_Sand_pct",
)


@dataclass(frozen=True)
class TrainingResult:
    model: RandomForestClassifier
    metrics: dict[str, object]
    feature_importances: dict[str, float]
    feature_stats: dict[str, dict[str, float]]
    split: dict[str, object]


def _spatial_holdout(
    data: CleanedDataset,
    test_size: float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, pd.Series]:
    if not 0.1 <= test_size <= 0.4:
        raise ValueError("test_size must be between 0.1 and 0.4")

    groups = spatial_groups(data.frame)
    if groups.nunique() < 5:
        raise ValueError("at least five spatial groups are required for a holdout")

    splitter = GroupShuffleSplit(n_splits=32, test_size=test_size, random_state=random_state)
    for train_index, test_index in splitter.split(data.frame, data.frame[TARGET_COLUMN], groups):
        train_labels = set(data.frame.iloc[train_index][TARGET_COLUMN].unique())
        test_labels = set(data.frame.iloc[test_index][TARGET_COLUMN].unique())
        if train_labels == {0, 1} and test_labels == {0, 1}:
            return train_index, test_index, groups
    raise ValueError("could not create a spatial holdout containing both target classes")


def train_and_evaluate(
    data: CleanedDataset,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> TrainingResult:
    train_index, test_index, groups = _spatial_holdout(data, test_size, random_state)
    frame = data.frame
    x_train = frame.iloc[train_index].loc[:, FEATURE_COLUMNS]
    x_test = frame.iloc[test_index].loc[:, FEATURE_COLUMNS]
    y_train = frame.iloc[train_index][TARGET_COLUMN]
    y_test = frame.iloc[test_index][TARGET_COLUMN]

    model = RandomForestClassifier(
        n_estimators=50,
        max_depth=8,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    probability = model.predict_proba(x_test)[:, list(model.classes_).index(1)]
    predicted = (probability >= 0.5).astype(int)
    matrix = confusion_matrix(y_test, predicted, labels=[0, 1])

    metrics: dict[str, object] = {
        "accuracy": float(accuracy_score(y_test, predicted)),
        "precision": float(precision_score(y_test, predicted, zero_division=0)),
        "recall": float(recall_score(y_test, predicted, zero_division=0)),
        "f1": float(f1_score(y_test, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probability)),
        "pr_auc": float(average_precision_score(y_test, probability)),
        "confusion_matrix": matrix.tolist(),
        "false_positives": int(matrix[0, 1]),
        "false_negatives": int(matrix[1, 0]),
        "train_samples": int(len(train_index)),
        "test_samples": int(len(test_index)),
        "initial_rows": data.initial_rows,
        "clean_rows": int(len(frame)),
        "duplicate_rows_removed": data.duplicate_rows,
    }
    importances = {
        feature: float(importance)
        for feature, importance in zip(FEATURE_COLUMNS, model.feature_importances_, strict=True)
    }
    split = {
        "strategy": "spatial_group_holdout",
        "cell_size_degrees": 0.25,
        "train_groups": int(groups.iloc[train_index].nunique()),
        "test_groups": int(groups.iloc[test_index].nunique()),
        "group_overlap": sorted(
            set(groups.iloc[train_index]).intersection(groups.iloc[test_index])
        ),
        "random_state": random_state,
    }
    return TrainingResult(
        model=model,
        metrics=metrics,
        feature_importances=importances,
        feature_stats=feature_statistics(frame, FEATURE_COLUMNS),
        split=split,
    )


def predict_probability(model: RandomForestClassifier, values: dict[str, float]) -> float:
    missing = [feature for feature in FEATURE_COLUMNS if feature not in values]
    if missing:
        raise ValueError(f"prediction is missing features: {', '.join(missing)}")
    row = pd.DataFrame([[float(values[name]) for name in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    return float(model.predict_proba(row)[0, list(model.classes_).index(1)])
