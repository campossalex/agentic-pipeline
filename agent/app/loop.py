"""The agent loop: LLM + Agent Skills + Context + Actions.

Each run opens an MCP session through agentgateway, builds the system prompt
from AGENTS.md and the skill catalog, then alternates model turns and tool
calls until the model answers without calling a tool (or MAX_STEPS is hit).
Everything the loop does is reported through `emit` as Open Responses items
and trace events, which the UI and A2A server render.
"""
import json
import time
from typing import Awaitable, Callable

from . import config, context, llm, skills
from .mcp_tools import Toolbox

Emit = Callable[[dict], Awaitable[None]]

SYSTEM_TEMPLATE = """You are the AAIF reference agent, a developer and knowledge assistant.
You work on files in /workspace through MCP tools and answer with what you actually found or did.

# How you work
- Skills hold tested procedures. When a request matches a skill below, call `activate_skill` first and follow it.
- Before working inside a project directory, call `load_project_context` with its path.
- Use tools to look things up instead of guessing. Cite file paths and URLs you used.
- Tool names are prefixed by the MCP server behind the gateway: fs_* (files), git_* (git), web_* (fetch URLs),
  sandbox_* (run code in an isolated OpenSandbox container), milvus_* (search indexed docs, if enabled).
- Some tools may be denied by gateway policy; if so, say so and continue without them.
- Keep the final answer concise and in Markdown.

# Installed skills
{skills}

# Workspace context (from /workspace/AGENTS.md)
{agents_md}
"""


def _trace(layer: str, title: str, detail=None, **extra) -> dict:
    return {"kind": "trace", "layer": layer, "title": title, "detail": detail, "ts": time.time(), **extra}


_CONTEXT_TOOLS = ("milvus_", "web_", "fs_read", "fs_list", "fs_search", "fs_directory", "fs_get",
                  "git_git_log", "git_git_status", "git_git_diff", "git_git_show")


def _layer_for(tool_name: str) -> str:
    """Read-only lookups count as context; anything that changes state is an action."""
    return "context" if tool_name.startswith(_CONTEXT_TOOLS) else "action"


async def run(items: list[dict], model: str, emit: Emit, instructions: str | None = None) -> tuple[list[dict], dict]:
    """Run the agent over the conversation `items`; returns (output items, usage)."""
    installed = skills.discover()
    agents_md = context.root_agents_md()
    system = SYSTEM_TEMPLATE.format(
        skills=skills.catalog_prompt(installed),
        agents_md=agents_md or "(none)",
    )
    if instructions:
        system += f"\n# Additional instructions\n{instructions}\n"

    await emit(_trace("context", "Loaded workspace AGENTS.md" if agents_md else "No workspace AGENTS.md",
                      {"path": str(config.WORKSPACE_DIR / "AGENTS.md")} if agents_md else None))
    await emit(_trace("skill", f"Skill catalog: {len(installed)} skills (names + descriptions only)",
                      [{"name": s.name, "description": s.description} for s in installed.values()]))

    output: list[dict] = []
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    async with Toolbox() as toolbox:
        if toolbox.error:
            await emit(_trace("action", "MCP gateway unavailable; continuing without MCP tools",
                              toolbox.error, status="error"))
        else:
            await emit(_trace("action", f"MCP tools via agentgateway: {len(toolbox.specs)}",
                              sorted(t["name"] for t in toolbox.specs)))
        tools = skills.TOOL_SPECS + [context.TOOL_SPEC] + toolbox.specs

        for step in range(1, config.MAX_STEPS + 1):
            await emit(_trace("llm", f"Model turn {step} → {model}", None, step=step))
            started = time.time()
            new_items, turn_usage = await llm.complete(model, system, items + output, tools)
            for key in usage:
                usage[key] += turn_usage.get(key, 0)
            await emit(_trace("llm", f"Model replied in {time.time() - started:.1f}s", turn_usage, step=step))

            if not new_items:  # e.g. a small local model that only produced hidden reasoning
                await emit(_trace("llm", "Model returned an empty reply", None, step=step, status="error"))
                new_items = [llm.assistant_message(
                    "The model returned an empty reply. Try again, or switch to a larger model.")]

            calls = []
            for item in new_items:
                output.append(item)
                await emit({"kind": "item", "item": item})
                if item["type"] == "function_call":
                    calls.append(item)
            if not calls:
                break

            for call in calls:
                result = await _dispatch(call, installed, toolbox, emit)
                out = llm.function_call_output(call["call_id"], result)
                output.append(out)
                await emit({"kind": "item", "item": out})
        else:
            note = llm.assistant_message(f"Stopped after {config.MAX_STEPS} steps without a final answer.")
            output.append(note)
            await emit({"kind": "item", "item": note})

    return output, usage


async def _dispatch(call: dict, installed: dict, toolbox: Toolbox, emit: Emit) -> str:
    name = call["name"]
    try:
        args = json.loads(call.get("arguments") or "{}")
    except json.JSONDecodeError:
        return f"Invalid JSON arguments for {name}: {call.get('arguments')}"

    if name == "activate_skill":
        result = skills.activate(installed, args.get("name", ""))
        await emit(_trace("skill", f"Activated skill: {args.get('name')}", result[:4000], call_id=call["call_id"]))
        return result
    if name == "read_skill_file":
        result = skills.read_file(installed, args.get("skill", ""), args.get("path", ""))
        await emit(_trace("skill", f"Read skill file: {args.get('skill')}/{args.get('path')}",
                          result[:4000], call_id=call["call_id"]))
        return result
    if name == "load_project_context":
        result, paths = context.load_project_context(args.get("path", ""))
        await emit(_trace("context", f"AGENTS.md chain for {args.get('path')}", paths, call_id=call["call_id"]))
        return result
    if toolbox.has(name):
        layer = _layer_for(name)
        await emit(_trace(layer, f"MCP call: {name}", args, call_id=call["call_id"]))
        started = time.time()
        text, is_error = await toolbox.call(name, args)
        await emit(_trace(layer, f"MCP result: {name} ({time.time() - started:.1f}s)", text[:4000],
                          call_id=call["call_id"], status="error" if is_error else "ok"))
        return f"ERROR: {text}" if is_error else text
    await emit(_trace("action", f"Unknown tool: {name}", None, status="error"))
    return f"Unknown tool '{name}'."
