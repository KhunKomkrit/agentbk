"""MCP server config — persisted as ~/.agentbk/mcp_servers.json."""
from __future__ import annotations
import json
from pathlib import Path

MCP_CONFIG_PATH = Path("~/.agentbk/mcp_servers.json").expanduser()

# Preset URLs for quick-add
MCP_PRESETS: list[dict] = [
    {"label": "Space MCP (local)", "url": "http://localhost:8000/mcp"},
    {"label": "JIRA",              "url": "http://localhost:9000/mcp"},
    {"label": "Google Calendar",   "url": "http://localhost:9001/mcp"},
    {"label": "Custom URL",        "url": ""},
]


def load_servers() -> list[dict]:
    """Return list of server dicts. Returns [] if file missing or corrupt."""
    if not MCP_CONFIG_PATH.exists():
        return []
    try:
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_servers(servers: list[dict]) -> None:
    """Atomically write server list to disk."""
    MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MCP_CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(servers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(MCP_CONFIG_PATH)
