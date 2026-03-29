"""OpenAI provider — GPT via official openai SDK."""
from __future__ import annotations
import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.providers.base import BaseLLMProvider, ToolCallRequest


class OpenAIProvider(BaseLLMProvider):
    name = "openai"
    supports_vision = True  # gpt-4o and gpt-4o-mini both accept image_url blocks.

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Any:
        kwargs: dict = dict(model=self.model, messages=messages, stream=False)
        if tools:
            kwargs["tools"] = tools
        return await self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    async def stream_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> AsyncIterator[str | list[ToolCallRequest]]:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,        # type: ignore[arg-type]
            stream=True,
        )
        tool_calls_acc: dict[int, dict] = {}
        async for chunk in response:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta  = choice.delta
            if delta.content:
                yield delta.content
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments
            if choice.finish_reason == "tool_calls":
                yield [
                    ToolCallRequest(id=v["id"], name=v["name"], arguments=v["arguments"])
                    for v in tool_calls_acc.values()
                ]
                return
