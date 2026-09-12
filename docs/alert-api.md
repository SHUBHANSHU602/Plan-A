# Alert API and lifecycle

## Read endpoints

```http
GET /api/v1/alerts?status=ACTIVE&severity=CRITICAL&cell_code=A17&limit=50
GET /api/v1/alerts/{alert_id}
```

The list endpoint uses an opaque cursor returned as `next_cursor`; clients should send that value
unchanged on the next request. Results use keyset pagination ordered by immutable alert creation
time and alert ID, avoiding offset drift. Filters can still change membership between requests if
another process changes an alert's status. The detail endpoint includes the append-only event
history.
Cooldown-suppressed evaluations update the alert's occurrence count and last-seen time without
writing one audit row per scheduler tick.

## Lifecycle endpoints

```http
POST /api/v1/alerts/{alert_id}/acknowledge
POST /api/v1/alerts/{alert_id}/verify
POST /api/v1/alerts/{alert_id}/resolve
```

Request:

```json
{
  "actor_reference": "district-admin",
  "note": "Field team dispatched"
}
```

Allowed state sequence:

```text
ACTIVE -> ACKNOWLEDGED -> VERIFIED -> RESOLVED
```

Repeating the current transition is idempotent and does not append a duplicate event. Skipping a
stage or moving backward returns `409 Conflict`. Unknown alert IDs return `404`, and malformed
filters or cursors return `422`.

`actor_reference` is deliberately recorded as a client-supplied reference (`actor_type=CLIENT`).
It is not a verified identity until authentication middleware replaces it with claims from a
trusted token.
