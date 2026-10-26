import os
from pathlib import Path

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:4000").rstrip("/")
MCP_URL = os.environ.get("MCP_URL", "http://localhost:3001/mcp")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "openai/gpt-5.5")
AVAILABLE_MODELS = [
    m.strip() for m in os.environ.get("AVAILABLE_MODELS", DEFAULT_MODEL).split(",") if m.strip()
]
if DEFAULT_MODEL not in AVAILABLE_MODELS:
    AVAILABLE_MODELS.insert(0, DEFAULT_MODEL)
MAX_STEPS = int(os.environ.get("MAX_STEPS", "24"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "8192"))
TOOL_OUTPUT_LIMIT = int(os.environ.get("TOOL_OUTPUT_LIMIT", "24000"))
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", "/skills"))
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8080").rstrip("/")
