# Runbook: deploying Tasky

1. Merge to `main`; CI runs `pytest` and `ruff check`.
2. CI builds the image `registry.internal/tasky:<git-sha>`.
3. Promote to staging: `deployctl promote tasky --env staging --sha <git-sha>`.
4. Smoke test: `curl -fsS https://tasky.staging.internal/todos`.
5. Promote to production during the change window (Tue–Thu, 09:00–16:00 CET):
   `deployctl promote tasky --env prod --sha <git-sha>`.
6. Rollback: `deployctl rollback tasky --env prod` restores the previous image; the SQLite
   file is not touched by rollbacks, so schema changes need a manual down-migration.
