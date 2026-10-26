"""Agent Skills (agentskills.io) with progressive disclosure.

1. Discovery: only `name` + `description` from each SKILL.md frontmatter go into
   the system prompt.
2. Activation: the model calls `activate_skill` and the full SKILL.md body is
   returned as a tool result.
3. Execution: the model reads bundled files on demand with `read_skill_file`
   (scripts, references, assets) and acts with MCP tools.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config


@dataclass
class Skill:
    name: str
    description: str
    root: Path
    body: str
    metadata: dict = field(default_factory=dict)

    def files(self) -> list[str]:
        return sorted(
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file() and p.name != "SKILL.md"
        )


def _parse(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front) or {}
    if not meta.get("name") or not meta.get("description"):
        return None
    return Skill(
        name=str(meta["name"]),
        description=" ".join(str(meta["description"]).split()),
        root=path.parent,
        body=body.strip(),
        metadata=meta,
    )


def discover(skills_dir: Path = config.SKILLS_DIR) -> dict[str, Skill]:
    skills = {}
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        skill = _parse(path)
        if skill:
            skills[skill.name] = skill
    return skills


def catalog_prompt(skills: dict[str, Skill]) -> str:
    if not skills:
        return "No skills are installed."
    lines = [f"- {s.name}: {s.description}" for s in skills.values()]
    return "\n".join(lines)


TOOL_SPECS = [
    {
        "name": "activate_skill",
        "description": (
            "Load the full instructions of an installed Agent Skill. Call this as soon as a "
            "task matches a skill's description, before doing the work."
        ),
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Skill name from the catalog"}},
            "required": ["name"],
        },
    },
    {
        "name": "read_skill_file",
        "description": "Read a file bundled with a skill (scripts/, references/, assets/).",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "path": {"type": "string", "description": "Path relative to the skill folder"},
            },
            "required": ["skill", "path"],
        },
    },
]


def activate(skills: dict[str, Skill], name: str) -> str:
    skill = skills.get(name)
    if not skill:
        return f"Unknown skill '{name}'. Installed: {', '.join(skills) or 'none'}"
    files = skill.files()
    listing = "\n".join(f"- {f}" for f in files) if files else "(none)"
    return (
        f'<skill name="{skill.name}">\n{skill.body}\n</skill>\n\n'
        f"Bundled files (read with read_skill_file):\n{listing}"
    )


def read_file(skills: dict[str, Skill], name: str, rel_path: str) -> str:
    skill = skills.get(name)
    if not skill:
        return f"Unknown skill '{name}'."
    target = (skill.root / rel_path).resolve()
    if not target.is_relative_to(skill.root.resolve()) or not target.is_file():
        return f"No file '{rel_path}' in skill '{name}'."
    return target.read_text(encoding="utf-8", errors="replace")
