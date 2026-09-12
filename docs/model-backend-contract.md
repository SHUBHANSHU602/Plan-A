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
alert policy, deduplication, and notification delivery. `MockModelGateway` is a
temporary deterministic integration adapter and is not a scientific prediction
model; it must be replaced when the trained artifact is delivered.
