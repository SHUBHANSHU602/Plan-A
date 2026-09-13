# Model/backend contract

The ML implementation is hidden behind `ModelGateway`. The backend supplies these
validated inference features:

```json
{
  "latitude": 27.19343,
  "longitude": 93.78098,
  "elevation_m": 213,
  "slope_deg": 50.76,
  "aspect_deg": 22.93,
  "rainfall_mm": 115.34
}
```

The model adapter must return:

```json
{
  "probability": 0.87,
  "predicted_class": 1,
  "drivers": ["High rainfall", "Steep slope"]
}
```

The backend—not the model—owns risk-level thresholds, persistence, exposure,
alert policy, deduplication, and notification delivery.

The reviewed artifact adapter also accepts these enriched fields:

```json
{
  "rainfall_7day_antecedent_mm": 240.0,
  "rainfall_event_era5_mm": 135.0,
  "soil_clay_pct": 35.5,
  "soil_sand_pct": 28.0
}
```

They are optional during the MVP transition. If omitted, the adapter uses training
medians recorded in the checksum-verified manifest, which is reduced-context inference.
Set `MODEL_PROVIDER=artifact` to use the reviewed model. The returned probability is a
classifier score for class `1`, not a calibrated guarantee that a landslide will occur.
Driver strings are transparent percentile rules, not SHAP values. `MockModelGateway`
remains available only as an explicit local/test fallback.
