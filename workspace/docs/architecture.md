# Tasky architecture

Tasky is a single Flask service backed by SQLite. It is deployed as one container per
environment behind the internal load balancer.

## Components

- **API** (`src/todo/app.py`): REST endpoints `GET /todos`, `POST /todos`,
  `POST /todos/<id>/done`. No authentication; it is only reachable on the internal network.
- **Store** (`src/todo/store.py`): `TodoStore` wraps a SQLite connection. The database path
  comes from the `TASKY_DB` environment variable; the default `:memory:` is for tests only.

## Data

Production uses a SQLite file on a persistent volume at `/data/tasky.db`. Backups run nightly
at 02:00 UTC by copying the file with `sqlite3 .backup` to object storage, retained 30 days.

## Limits

SQLite serializes writes. Above roughly 50 writes per second we see `database is locked`
errors; see the runbook. ADR-002 records the decision to migrate to Postgres when sustained
load passes that threshold.
