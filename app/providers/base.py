"""Base LLM provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ToolCallRequest:
    """Emitted by stream_tools() when the model wants to call a tool."""
    id:        str
    name:      str
    arguments: str   # JSON string


class BaseLLMProvider(ABC):
    name: str
    model: str
    # True when this provider+model can accept image content blocks.
    supports_vision: bool = False

    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Stream plain text response tokens (no tool calling)."""
        ...

    @abstractmethod
    async def stream_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> AsyncIterator[str | list[ToolCallRequest]]:
        """Stream response with tool-call support.

        Yields:
        - str   — text token
        - list[ToolCallRequest]  — tool calls requested (one batch at end)

        If the model returns tool calls, the generator ends with a single
        list[ToolCallRequest] item instead of a "done" str sentinel.
        If no tool calls, yields only str tokens.
        """
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Any:
        """Non-streaming completion. Returns the raw SDK response object."""
        ...
