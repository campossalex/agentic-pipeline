# ADR-002: Migrate Tasky to Postgres past 50 writes/second

- Status: accepted (2026-06-18)
- Supersedes: part of ADR-001 (storage)

## Context

Adoption grew to ~2,000 users. Peaks reached 35 writes/s in May 2026 and "database is locked"
incidents happened twice.

## Decision

Keep SQLite until sustained load exceeds 50 writes/s or a third locking incident occurs within
a quarter. Then migrate to the shared Postgres cluster, using SQLAlchemy so the store layer is
the only code that changes. Target: two replicas behind the load balancer.

## Consequences

- Migration effort estimated at two weeks including a data copy and a dual-write window.
- Local development will use Postgres in Docker Compose.
