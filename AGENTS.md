# AGENTS.md

Guidance for coding agents working on this repository (the AAIF Agent Stack).
The agent's own runtime context is `workspace/AGENTS.md`, not this file.

## Run

```bash
cp example.env .env   # add OPENAI_API_KEY and/or ANTHROPIC_API_KEY, or use --profile local
docker compose up -d --build
docker compose logs -f agent gateway
```

After changing `agent/app/*`: `docker compose up -d --build agent`.
After changing `gateway/config.yaml`: `docker compose restart gateway` (it also hot-reloads).
Skills and workspace files are mounted; changes apply on the next request.

## Check

```bash
curl -s localhost:8080/api/info | jq '.tools | length'   # MCP tools visible through the gateway
curl -s localhost:8080/v1/responses -H 'content-type: application/json' -d '{"input":"hi"}'
docker compose exec agent python /scripts/a2a_client.py "What skills do you have?"
```

## Layout

- `agent/app/main.py` — Open Responses endpoint, `/api/info`; A2A routes mounted last.
- `agent/app/loop.py` — agent loop and trace events (`layer`: llm, skill, context, action).
- `agent/app/llm.py` — Open Responses items ⇄ chat-completions via agentgateway.
- `agent/app/mcp_tools.py` — MCP client (`mcp` 2.x `Client`) to the gateway.
- `agent/app/skills.py`, `agent/app/context.py` — Agent Skills and AGENTS.md handling.
- `gateway/config.yaml` — agentgateway v1.6.0 config. Check field names against
  https://agentgateway.dev/schema/config for that version; main-branch features differ.

## Conventions

- Python 3.12, standard library first, type hints, module docstring explaining the layer.
- Tool names reaching the model are `<gateway target>_<upstream tool>`; skills must use those
  exact names (e.g. `git_git_log`, `sandbox_sandbox_create`).
- Pin image tags and package versions.
- Never commit `.env` or keys.
