"""MCP client — supports both HTTP (streamable-http/SSE) and stdio transports.

Transport selection
-------------------
* ``transport="http"``  (default) — connect via streamable-http to a remote URL.
  Headers (e.g. Authorization) are forwarded.
* ``transport="stdio"`` — spawn a local subprocess (e.g. ``uvx mcp-atlassian``)
  and communicate via stdin/stdout.  ``command``, ``args``, and ``env`` are used.

Both transports spawn a fresh connection/process per operation (safe across
asyncio.run() restarts called from different threads).
"""
from __future__ import annotations

import os
from typing import Any

# Import mcp modules at module level so Python's import lock is acquired once
# on first import, not inside multiple concurrent threads (deadlock risk).
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession


def _extract_tools(result_tools: list) -> tuple[list[dict], set[str]]:
    tools: list[dict] = []
    names: set[str] = set()
    for tool in result_tools:
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
        tools.append(schema)
        names.add(tool.name)
    return tools, names


class MCPClient:
    """Lazy-init MCP client supporting HTTP and stdio transports.

    HTTP server dict:   {"name": "…", "url": "http://…", "headers": {…}}
    Stdio server dict:  {"name": "…", "type": "stdio",
                         "command": "uvx", "args": ["mcp-atlassian"],
                         "env": {"JIRA_URL": "…", "JIRA_API_TOKEN": "…"}}
    """

    def __init__(
        self,
        name: str = "",
        *,
        # HTTP
        headers: dict | None = None,
        # Stdio
        transport: str = "http",
        command: str = "",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.name         = name
        self._transport   = transport         # "http" | "stdio"
        # HTTP
        self._headers     = headers or {}
        self._url         = ""
        # Stdio
        self._command     = command
        self._args        = args or []
        self._env: dict[str, str] = {**os.environ, **(env or {})}
        # Shared
        self._tools:      list[dict] = []
        self._tool_names: set[str]   = set()

    # ── HTTP transport ────────────────────────────────────────────────────

    async def connect(self, url: str) -> None:
        """Fetch tool schemas via HTTP. Fails silently if unreachable."""
        self._url        = url
        self._tools      = []
        self._tool_names = set()
        try:
            async with streamablehttp_client(url, headers=self._headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    self._tools, self._tool_names = _extract_tools(result.tools)
        except Exception:
            pass

    async def _http_call(self, name: str, arguments: dict[str, Any]) -> str:
        async with streamablehttp_client(self._url, headers=self._headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _content_to_str(result.content)

    # ── Stdio transport ───────────────────────────────────────────────────

    async def connect_stdio(self) -> None:
        """Spawn subprocess, fetch tool schemas, then terminate. Fails silently."""
        self._tools      = []
        self._tool_names = set()
        try:
            params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    self._tools, self._tool_names = _extract_tools(result.tools)
        except Exception:
            pass

    async def _stdio_call(self, name: str, arguments: dict[str, Any]) -> str:
        params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _content_to_str(result.content)

    # ── Unified API ───────────────────────────────────────────────────────

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool. Returns result as string."""
        if self._transport == "stdio":
            return await self._stdio_call(name, arguments)
        return await self._http_call(name, arguments)

    @property
    def tools(self) -> list[dict]:
        return self._tools

    def owns(self, tool_name: str) -> bool:
        return tool_name in self._tool_names


def _content_to_str(content: list) -> str:
    parts = []
    for c in content:
        if hasattr(c, "text"):
            parts.append(c.text)
        else:
            parts.append(str(c))
    return "\n".join(parts)
