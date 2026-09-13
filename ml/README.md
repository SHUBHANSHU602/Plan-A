# Reproducible landslide model pipeline

This directory trains and validates the tabular landslide-risk model. Model files are
generated outputs and are intentionally ignored by Git. A trained bundle is mergeable
only when its manifest, dataset fingerprint, scenario checks, and CI-compatible runtime
version are supplied with it.

## Expected dataset

The enriched CSV must contain these columns:

```text
Latitude
Longitude
Elevation_m
Slope_deg
Aspect_deg
Rainfall_mm
Rainfall_7day_antecedent_mm
Rainfall_Event_ERA5_mm
Soil_Clay_pct
Soil_Sand_pct
Landslide_Label
```

The training data is not committed because its licensing and provenance must be reviewed
separately. Put it under `data/raw/` locally.

## Train and verify

```bash
python -m pip install -e './ml[test]'
python ml/train.py \
  --data data/raw/GSI_NER_Fast_Enriched.csv \
  --output ml/artifacts
pytest ml/tests
```

Training uses a spatial group holdout rather than a random row split. Nearby samples in
the same 0.25-degree cell cannot appear in both training and test sets. This is still a
prototype validation strategy, not proof of operational generalization.

Generated files:

```text
ml/artifacts/landslide_model.joblib
ml/artifacts/model_manifest.json
```

The manifest records the exact feature order, model parameters, package versions,
dataset SHA-256, split metadata, metrics, feature statistics, and two demo scenario
probabilities. The training command fails if the documented dry scenario scores at or
above the monsoon scenario.

## Interpretation limits

- `probability` is the classifier score for class `1`; it is not a guaranteed event
  probability unless calibration is separately demonstrated.
- Driver strings are transparent threshold-based explanations, not SHAP values.
- Pseudo-absence labels and imputed environmental features must be disclosed.
- The backend owns operational risk levels, alert policy, deduplication, and delivery.
