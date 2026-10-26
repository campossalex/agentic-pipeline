"""Context layer: AGENTS.md (agents.md) files from the workspace.

The workspace-root AGENTS.md is always in the system prompt. When the agent
works inside a sub-project, `load_project_context` returns every AGENTS.md from
the workspace root down to that path; per the AGENTS.md convention the closest
file wins on conflicts. Further context (files, git history, web pages, the
Milvus index) is pulled on demand through MCP tools.
"""
from pathlib import Path

from . import config

ROOT_FILE = "AGENTS.md"


def root_agents_md() -> str | None:
    path = config.WORKSPACE_DIR / ROOT_FILE
    return path.read_text(encoding="utf-8") if path.is_file() else None


def agents_md_chain(path: str) -> list[tuple[str, str]]:
    """AGENTS.md files from the workspace root to `path`, outermost first."""
    root = config.WORKSPACE_DIR.resolve()
    target = Path(path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    if not target.is_relative_to(root):
        return []
    if target.is_file():
        target = target.parent
    found = []
    current = target
    while True:
        candidate = current / ROOT_FILE
        if candidate.is_file():
            found.append((str(candidate), candidate.read_text(encoding="utf-8")))
        if current == root:
            break
        current = current.parent
    return list(reversed(found))


TOOL_SPEC = {
    "name": "load_project_context",
    "description": (
        "Load the AGENTS.md guidance that applies to a path in /workspace (every AGENTS.md "
        "from the workspace root down to that path). Call it before working inside a project."
    ),
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Absolute path under /workspace"}},
        "required": ["path"],
    },
}


def load_project_context(path: str) -> tuple[str, list[str]]:
    chain = agents_md_chain(path)
    if not chain:
        return f"No AGENTS.md applies to {path}.", []
    parts = [f'<agents_md path="{p}">\n{text.strip()}\n</agents_md>' for p, text in chain]
    note = "Closest file wins on conflicts." if len(chain) > 1 else ""
    return "\n\n".join(parts + ([note] if note else [])), [p for p, _ in chain]
