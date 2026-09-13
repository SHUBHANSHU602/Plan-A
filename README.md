# Plan-A

Plan-A is a geospatial landslide risk and early-warning platform. The repository is
organized as a monorepo so the backend, ML pipeline, frontend, infrastructure, and
documentation can evolve independently while sharing one integration contract.

## Repository layout

```text
Plan-A/
├── backend/       FastAPI application, domain services, and API tests
├── frontend/      Web dashboard (implementation follows in a separate PR)
├── ml/            Model training and inference artifacts
├── data/          Dataset contracts and local-data guidance
├── docs/          Architecture and engineering decisions
└── infra/         Deployment and infrastructure configuration
```

## Run the backend

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e './backend[test]'
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --app-dir backend --reload
```

Open <http://127.0.0.1:8000/health> or the generated API documentation at
<http://127.0.0.1:8000/docs>.

The direct development command uses the deterministic mock unless
`MODEL_PROVIDER=artifact` is exported. Docker Compose enables the checksum-verified
Random Forest artifact by default. Optional antecedent-rainfall and soil inputs improve
the eight-feature prediction; omitted values use training medians recorded in the model
manifest and should be treated as reduced-context inference.

`/health` is a liveness probe and does not touch the database. `/health/ready`
checks database availability and should be used as the deployment readiness probe.

## Live alert stream

Dashboard clients connect to `ws://127.0.0.1:8000/ws/alerts`. The server first sends
`{"type":"connection.ready","version":"1"}` and then emits committed alert creation,
refresh, escalation, and lifecycle events as `alert.event` messages. Clients may send
`{"type":"ping"}` and receive `{"type":"pong"}`.

The stream is a best-effort live transport. A reconnecting client must use
`GET /api/v1/alerts` to reconcile anything missed while disconnected. The current
prototype has no WebSocket authentication, so production deployments must keep it
behind a trusted gateway until application authentication is added.

## Push notifications

Clients register an FCM installation ID with
`POST /api/v1/notifications/subscriptions` and may deactivate it with
`DELETE /api/v1/notifications/subscriptions/{subscription_id}`. Installation IDs
are stored for delivery but are never returned by the API. Delivery outcomes are
available from `GET /api/v1/notifications/deliveries?alert_id={alert_id}`.

FCM is disabled by default. Enable it with `FCM_ENABLED=true`, set
`FCM_PROJECT_ID`, and provide Google Application Default Credentials through the
deployment environment. Never commit a service-account JSON file. Transient failures
use bounded exponential backoff; invalid/expired targets are deactivated. PR9 wires
the exposed retry operation into the application scheduler.

The subscription endpoints currently share the prototype's unauthenticated API
boundary. Put the service behind a trusted gateway until application authentication
and per-user authorization are implemented.

## Rainfall operations and simulation

External rainfall adapters enqueue idempotent updates with
`POST /api/v1/rainfall/observations`; the `(source, source_event_id)` pair prevents
duplicate processing. The scheduler claims due observations, runs the same persisted
risk/alert/notification pipeline used by `POST /api/v1/predict`, and retries transient
processing failures with bounded backoff. Stale claims are recoverable after the
configured timeout.

`POST /api/v1/simulation/rainfall` multiplies either the latest persisted rainfall or
an explicitly supplied baseline and returns the resulting prediction and alert. The
artifact gateway is enabled by Docker Compose. The mock gateway remains available only
as an explicit local/test fallback; its coefficients are not scientific thresholds.

Both operational endpoints currently use the prototype's trusted-gateway boundary.
They can create alerts and dispatch configured notification channels, so production
deployments must restrict them to authenticated ingestion workers and administrators;
run simulations with sandbox notification recipients.

APScheduler starts with the API process by default. It coalesces missed intervals and
limits each job to one local instance; database row claiming protects queued work
when multiple API replicas run. Disable background processing with
`SCHEDULER_ENABLED=false` when running a dedicated scheduler process.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

The API is available on port `8000`; PostgreSQL/PostGIS is available on port
`5432` for local development.

## Quality checks

```bash
ruff check backend
ruff format --check backend
pytest backend/tests
```

Pull requests must pass linting, formatting, tests, and a backend container build.
Merges to `main` publish a versioned backend image to GitHub Container Registry.
