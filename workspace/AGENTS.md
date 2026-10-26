# Workspace

This is the agent's working directory, mounted at `/workspace` in every MCP server.

## What's here

- `sample-app/` — "Tasky", a small Python todo service (Flask + SQLite). Git repository.
- `docs/` — internal engineering docs: architecture, runbooks, ADRs. Indexed into Milvus when
  the `rag` profile is on.
- `data/` — CSV datasets for analysis (`sales.csv`: monthly revenue by region and product).
- `briefs/` — research briefs written by the agent.
- `reports/` — analysis reports written by the agent.

## Rules for agents

- Write new files only under `briefs/`, `reports/`, or inside a project when the user asks for
  a change there (an `AGENTS.md`, a fix).
- Never delete files. Never rewrite git history.
- Code is executed only in OpenSandbox, never assumed.
- Projects may contain their own `AGENTS.md`; call `load_project_context` before working in one.
