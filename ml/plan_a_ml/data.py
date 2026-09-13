from dataclasses import dataclass

import numpy as np
import pandas as pd

TARGET_COLUMN = "Landslide_Label"
LATITUDE_COLUMN = "Latitude"
LONGITUDE_COLUMN = "Longitude"

FEATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "Elevation_m": (0.0, 8_848.0),
    "Slope_deg": (0.0, 90.0),
    "Aspect_deg": (0.0, 360.0),
    "Rainfall_mm": (0.0, 2_500.0),
    "Rainfall_7day_antecedent_mm": (0.0, 10_000.0),
    "Rainfall_Event_ERA5_mm": (0.0, 2_500.0),
    "Soil_Clay_pct": (0.0, 100.0),
    "Soil_Sand_pct": (0.0, 100.0),
}


@dataclass(frozen=True)
class CleanedDataset:
    frame: pd.DataFrame
    initial_rows: int
    dropped_rows: int
    duplicate_rows: int
    class_counts: dict[int, int]


def clean_dataset(frame: pd.DataFrame, feature_columns: tuple[str, ...]) -> CleanedDataset:
    required = {LATITUDE_COLUMN, LONGITUDE_COLUMN, TARGET_COLUMN, *feature_columns}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"dataset is missing required columns: {', '.join(missing)}")

    selected = frame.loc[:, sorted(required)].copy()
    initial_rows = len(selected)
    for column in required:
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    selected = selected.replace([np.inf, -np.inf], np.nan).dropna()

    valid = (
        selected[LATITUDE_COLUMN].between(-90, 90)
        & selected[LONGITUDE_COLUMN].between(-180, 180)
        & selected[TARGET_COLUMN].isin([0, 1])
    )
    for column, (minimum, maximum) in FEATURE_BOUNDS.items():
        if column in feature_columns:
            valid &= selected[column].between(minimum, maximum)

    selected = selected.loc[valid].copy()
    rows_before_deduplication = len(selected)
    selected = selected.drop_duplicates(subset=sorted(required)).copy()
    duplicate_rows = rows_before_deduplication - len(selected)
    selected[TARGET_COLUMN] = selected[TARGET_COLUMN].astype(int)
    class_counts = {
        int(label): int(count) for label, count in selected[TARGET_COLUMN].value_counts().items()
    }
    if set(class_counts) != {0, 1}:
        raise ValueError("clean dataset must contain both Landslide_Label classes 0 and 1")
    if min(class_counts.values()) < 20:
        raise ValueError("each target class must contain at least 20 clean rows")

    return CleanedDataset(
        frame=selected,
        initial_rows=initial_rows,
        dropped_rows=initial_rows - len(selected),
        duplicate_rows=duplicate_rows,
        class_counts=class_counts,
    )


def spatial_groups(frame: pd.DataFrame, cell_size_degrees: float = 0.25) -> pd.Series:
    if cell_size_degrees <= 0:
        raise ValueError("cell_size_degrees must be positive")
    latitude_bin = np.floor(frame[LATITUDE_COLUMN] / cell_size_degrees).astype(int)
    longitude_bin = np.floor(frame[LONGITUDE_COLUMN] / cell_size_degrees).astype(int)
    return latitude_bin.astype(str) + ":" + longitude_bin.astype(str)


def feature_statistics(
    frame: pd.DataFrame, feature_columns: tuple[str, ...]
) -> dict[str, dict[str, float]]:
    return {
        column: {
            "min": float(frame[column].min()),
            "p25": float(frame[column].quantile(0.25)),
            "median": float(frame[column].median()),
            "p75": float(frame[column].quantile(0.75)),
            "max": float(frame[column].max()),
        }
        for column in feature_columns
    }
