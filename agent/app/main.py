"""HTTP surface of the agent.

- POST /v1/responses   Open Responses API (JSON or SSE), with `aaif.trace` extension events
- GET  /api/info       models, skills and MCP tools, for the UI
- A2A                  /.well-known/agent-card.json, /a2a/jsonrpc, /a2a/rest
"""
import asyncio
import json
import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import a2a_server, config, context, llm, loop, skills
from .mcp_tools import list_tools

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="AAIF reference agent")

# previous_response_id -> full conversation (input + output items). In-memory only.
_conversations: dict[str, list[dict]] = {}


class ResponsesRequest(BaseModel):
    model: str | None = None
    input: Any
    instructions: str | None = None
    previous_response_id: str | None = None
    stream: bool = False


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/api/info")
async def info():
    tools, error = await list_tools()
    return {
        "models": config.AVAILABLE_MODELS,
        "default_model": config.DEFAULT_MODEL,
        "skills": [{"name": s.name, "description": s.description, "files": s.files()}
                   for s in skills.discover().values()],
        "tools": [{"name": t["name"], "description": t["description"]} for t in tools],
        "mcp_error": error,
        "agents_md": context.root_agents_md() is not None,
    }


def _response_object(resp_id: str, model: str, status: str, output: list[dict],
                      usage: dict | None, created: int, error: dict | None = None) -> dict:
    return {
        "id": resp_id,
        "object": "response",
        "created_at": created,
        "status": status,
        "model": model,
        "output": output,
        "usage": usage,
        "error": error,
    }


def _prepare(req: ResponsesRequest) -> tuple[str, list[dict], list[dict]]:
    model = req.model or config.DEFAULT_MODEL
    history: list[dict] = []
    if req.previous_response_id:
        if req.previous_response_id not in _conversations:
            raise HTTPException(404, f"Unknown previous_response_id {req.previous_response_id}")
        history = list(_conversations[req.previous_response_id])
    return model, history, llm.normalize_input(req.input)


@app.post("/v1/responses")
async def create_response(req: ResponsesRequest):
    model, history, new_input = _prepare(req)
    resp_id = llm.new_id("resp")
    created = int(time.time())
    items = history + new_input

    if not req.stream:
        async def ignore(_: dict) -> None:
            return None
        try:
            output, usage = await loop.run(items, model, ignore, req.instructions)
        except llm.LLMError as exc:
            return JSONResponse(_response_object(resp_id, model, "failed", [], None, created,
                                                 {"code": "model_error", "message": str(exc)}), status_code=502)
        _conversations[resp_id] = items + output
        return _response_object(resp_id, model, "completed", output, usage, created)

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def worker() -> None:
        try:
            output, usage = await loop.run(items, model, emit, req.instructions)
            _conversations[resp_id] = items + output
            await queue.put({"kind": "done", "output": output, "usage": usage})
        except Exception as exc:  # surfaced to the client as response.failed
            logging.exception("agent run failed")
            await queue.put({"kind": "failed", "message": str(exc)})

    async def events():
        seq = 0
        output: list[dict] = []

        def sse(event_type: str, payload: dict) -> str:
            nonlocal seq
            seq += 1
            return f"event: {event_type}\ndata: {json.dumps({'type': event_type, 'sequence_number': seq, **payload})}\n\n"

        base = _response_object(resp_id, model, "in_progress", [], None, created)
        yield sse("response.created", {"response": base})
        yield sse("response.in_progress", {"response": base})
        task = asyncio.create_task(worker())
        try:
            while True:
                event = await queue.get()
                if event["kind"] == "trace":
                    yield sse("aaif.trace", {"trace": event})
                elif event["kind"] == "item":
                    item = event["item"]
                    idx = len(output)
                    output.append(item)
                    yield sse("response.output_item.added", {"output_index": idx, "item": item})
                    if item["type"] == "message":
                        text = llm.message_text(item)
                        common = {"item_id": item["id"], "output_index": idx, "content_index": 0}
                        yield sse("response.output_text.delta", {**common, "delta": text})
                        yield sse("response.output_text.done", {**common, "text": text})
                    yield sse("response.output_item.done", {"output_index": idx, "item": item})
                elif event["kind"] == "done":
                    done = _response_object(resp_id, model, "completed", event["output"], event["usage"], created)
                    yield sse("response.completed", {"response": done})
                    break
                elif event["kind"] == "failed":
                    failed = _response_object(resp_id, model, "failed", output, None, created,
                                              {"code": "agent_error", "message": event["message"]})
                    yield sse("response.failed", {"response": failed})
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# Mounted last: the A2A REST routes include tenant-prefixed patterns that would shadow /api/*.
a2a_server.mount(app)
