import argparse
import json
from pathlib import Path

import pandas as pd

from plan_a_ml.artifacts import save_bundle
from plan_a_ml.data import clean_dataset
from plan_a_ml.pipeline import FEATURE_COLUMNS, train_and_evaluate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and package the Plan-A landslide model")
    parser.add_argument("--data", type=Path, required=True, help="path to the enriched CSV")
    parser.add_argument("--output", type=Path, default=Path("ml/artifacts"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = pd.read_csv(args.data)
    cleaned = clean_dataset(raw, FEATURE_COLUMNS)
    result = train_and_evaluate(cleaned)
    manifest = save_bundle(result, args.data, args.output)
    summary = {
        "initial_rows": cleaned.initial_rows,
        "clean_rows": len(cleaned.frame),
        "dropped_rows": cleaned.dropped_rows,
        "class_counts": cleaned.class_counts,
        "metrics": manifest["metrics"],
        "split": manifest["split"],
        "demo_scenarios": manifest["demo_scenarios"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
