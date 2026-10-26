# Runbook: "database is locked" errors

## Symptoms

- API returns HTTP 500 on `POST /todos` with `sqlite3.OperationalError: database is locked`
  in the logs.
- p99 latency on write endpoints above 2 seconds.

## Immediate mitigation

1. Check for a long-running backup: a nightly `sqlite3 .backup` holding the lock past 02:15 UTC
   is the most common cause. If one is stuck, stop it; the next run will retry.
2. Scale the service down to **one** replica. Multiple replicas writing the same SQLite file
   over a network volume make locking much worse.
3. Set `TASKY_SQLITE_TIMEOUT=10` (seconds) so writers wait instead of failing immediately,
   and restart.

## Follow-up

- Record the incident with the peak write rate. If it exceeded 50 writes/s, raise priority of
  the Postgres migration (ADR-002).
- Owner: platform team, on-call rotation "tasky-oncall".
