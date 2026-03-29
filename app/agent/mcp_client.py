"""MCP client — connects to FastMCP server via streamable-http transport."""
from __future__ import annotations
import json
from typing import Any


class MCPClient:
    """Lazy-init MCP client. Fetches tool schemas on connect().
    Each call_tool() opens a fresh HTTP session (safe across asyncio restarts)."""

    def __init__(self, name: str = "", headers: dict | None = None) -> None:
        self.name:        str       = name
        self._headers:    dict      = headers or {}
        self._url:        str       = ""
        self._tools:      list[dict] = []
        self._tool_names: set[str]   = set()

    async def connect(self, url: str) -> None:
        """Fetch available tools from the MCP server. Fails silently if unreachable."""
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        self._url        = url
        self._tools      = []
        self._tool_names = set()
        try:
            async with streamablehttp_client(url, headers=self._headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    for tool in result.tools:
                        schema = {
                            "type": "function",
                            "function": {
                                "name":        tool.name,
                                "description": tool.description or "",
                                "parameters":  (
                                    tool.inputSchema
                                    if tool.inputSchema
                                    else {"type": "object", "properties": {}, "required": []}
                                ),
                            },
                        }
                        self._tools.append(schema)
                        self._tool_names.add(tool.name)
        except Exception:
            pass   # server unreachable — tools stay empty, degraded gracefully

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool on the MCP server. Returns result as string."""
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        async with streamablehttp_client(self._url, headers=self._headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                parts = []
                for c in result.content:
                    if hasattr(c, "text"):
                        parts.append(c.text)
                    else:
                        parts.append(str(c))
                return "\n".join(parts)

    @property
    def tools(self) -> list[dict]:
        return self._tools

    def owns(self, tool_name: str) -> bool:
        return tool_name in self._tool_names
