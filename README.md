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
