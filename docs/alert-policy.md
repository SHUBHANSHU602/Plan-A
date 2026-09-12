# Alert policy and deduplication

The alert engine evaluates every persisted risk snapshot. `LOW` and `MEDIUM` snapshots do not
create alerts. `HIGH` and `CRITICAL` snapshots create or update one open alert for the risk cell.
These are configurable operational risk categories, not claims that a landslide will occur.

## Deduplication actions

| Action | Meaning |
| --- | --- |
| `CREATED` | No open alert existed for the cell. |
| `SUPPRESSED` | The same or lower severity repeated inside the cooldown. State is updated, but a later notification dispatcher must not resend. |
| `REFRESHED` | The risk repeated after the cooldown and is eligible for redispatch. |
| `ESCALATED` | Severity increased from `HIGH` to `CRITICAL` and is immediately eligible for dispatch. |

The database enforces at most one open alert per cell. A transaction-scoped advisory lock also
serializes concurrent evaluations for the same cell, preventing the classic check-then-insert
race. Each alert retains current and peak probability, latest drivers, exposure counts, first and
last seen timestamps, the last dispatch-eligible timestamp, and an occurrence count.

Defaults:

```dotenv
ALERT_EXPOSURE_RADIUS_M=2000
ALERT_DEDUP_COOLDOWN_MINUTES=30
```

Notification delivery is intentionally outside this change. A later notifier should dispatch only
for `CREATED`, `REFRESHED`, and `ESCALATED`; it should never dispatch `SUPPRESSED` evaluations.
