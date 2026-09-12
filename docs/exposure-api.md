# Geospatial exposure API

The exposure API identifies stored infrastructure assets near a risk cell. Assets are stored as
indexed PostGIS `geography` values, so `radius_m` is measured in metres rather than coordinate
degrees and proximity queries can use the spatial index.

## Endpoint

```http
GET /api/v1/exposure/{cell_code}?radius_m=2000
```

The radius must be greater than zero and cannot exceed 50,000 metres. The response includes
type counts and individual assets ordered by their distance from the risk-cell boundary.

```json
{
  "cell_id": "b57e6017-ed48-47da-90bf-b1bbbd64d875",
  "cell_code": "A17",
  "radius_m": 2000,
  "total_assets": 2,
  "counts": {
    "VILLAGE": 1,
    "ROAD": 0,
    "HOSPITAL": 1,
    "SCHOOL": 0,
    "BRIDGE": 0,
    "RAILWAY": 0
  },
  "assets": []
}
```

The search radius is a configurable operational buffer for the prototype. It is not a
scientifically validated landslide-impact boundary.
