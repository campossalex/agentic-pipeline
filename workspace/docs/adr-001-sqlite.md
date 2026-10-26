# ADR-001: Use SQLite for Tasky storage

- Status: accepted (2025-03-04)

## Context

Tasky started as an internal tool with fewer than 100 users and a handful of writes per minute.

## Decision

Use SQLite on a persistent volume. One replica. Nightly file backups.

## Consequences

- No database server to operate; trivial local development.
- Single writer; horizontal scaling of the API is not possible without changing storage.
