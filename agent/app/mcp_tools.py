"""Actions layer: MCP tools, all reached through one agentgateway endpoint.

agentgateway multiplexes every MCP server and prefixes tool names with the
target name (fs_*, git_*, web_*, sandbox_*, milvus_*), applies authorization
rules, and masks secrets in results.
"""
import logging
import re
from contextlib import AsyncExitStack

from mcp import Client

from . import config

log = logging.getLogger(__name__)

_VALID = re.compile(r"[^a-zA-Z0-9_-]")


def _schema(schema) -> dict:
    if schema is None:
        return {"type": "object", "properties": {}}
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True, exclude_none=True)
    schema.setdefault("properties", {})
    return schema


class Toolbox:
    """One MCP session per agent run."""

    def __init__(self, url: str = config.MCP_URL):
        self.url = url
        self.client: Client | None = None
        self.specs: list[dict] = []
        self.error: str | None = None
        self._names: dict[str, str] = {}  # LLM-safe name -> MCP tool name
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "Toolbox":
        try:
            self.client = await self._stack.enter_async_context(Client(self.url))
            result = await self.client.list_tools()
        except Exception as exc:  # gateway down or no targets: run without tools
            log.warning("MCP unavailable: %s", exc)
            self.error = str(exc)
            await self._stack.aclose()
            self.client = None
            return self
        for tool in result.tools:
            safe = _VALID.sub("_", tool.name)[:64]
            self._names[safe] = tool.name
            self.specs.append({
                "name": safe,
                "description": (tool.description or "")[:1024],
                "parameters": _schema(tool.input_schema),
            })
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    def has(self, name: str) -> bool:
        return name in self._names

    async def call(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Returns (text output, is_error)."""
        if not self.client:
            return "MCP gateway unavailable", True
        try:
            result = await self.client.call_tool(self._names[name], arguments)
        except Exception as exc:
            return f"Tool call failed: {exc}", True
        parts = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
            elif getattr(block, "type", None) == "resource":
                parts.append(getattr(block.resource, "text", "") or str(block.resource.uri))
            else:
                parts.append(f"[{getattr(block, 'type', 'content')} omitted]")
        if not parts and result.structured_content is not None:
            parts.append(str(result.structured_content))
        text = "\n".join(parts)
        if len(text) > config.TOOL_OUTPUT_LIMIT:
            text = text[: config.TOOL_OUTPUT_LIMIT] + f"\n...[truncated {len(text)} chars]"
        return text, bool(result.is_error)


async def list_tools() -> tuple[list[dict], str | None]:
    async with Toolbox() as tb:
        return tb.specs, tb.error
