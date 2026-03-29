"""Anthropic provider — Claude via anthropic SDK, normalised to OpenAI response shape."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import anthropic

from app.providers.base import BaseLLMProvider, ToolCallRequest


# ── Fake OpenAI-shaped response ── keeps router.py unchanged ─────────────────

class _Function:
    def __init__(self, name: str, arguments: str) -> None:
        self.name      = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id: str, name: str, arguments: str) -> None:
        self.id       = id
        self.type     = "function"
        self.function = _Function(name, arguments)


class _Message:
    def __init__(self, tool_calls: list[_ToolCall] | None, content: str | None) -> None:
        self.tool_calls = tool_calls or None
        self.content    = content

    def model_dump(self, exclude_none: bool = False) -> dict:
        """Produce the OpenAI-format assistant message dict the router appends."""
        if self.tool_calls:
            return {
                "role": "assistant",
                "content": self.content or "",
                "tool_calls": [
                    {
                        "id":       tc.id,
                        "type":     "function",
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in self.tool_calls
                ],
            }
        return {"role": "assistant", "content": self.content or ""}


@dataclass
class _Choice:
    message: _Message


@dataclass
class _FakeResponse:
    choices: list[_Choice]


# ── Provider ──────────────────────────────────────────────────────────────────

class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    supports_vision = True  # All Claude 3+ models accept image content blocks.

    def __init__(self) -> None:
        self.model  = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self._client = anthropic.AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )

    # ── complete ──────────────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Any:
        system   = _extract_system(messages)
        converted = _convert_messages(messages)
        kwargs: dict = dict(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=converted,
        )
        if tools:
            kwargs["tools"] = _convert_tools(tools)

        response = await self._client.messages.create(**kwargs)

        # Parse Anthropic response → fake OpenAI shape
        tool_calls: list[_ToolCall] = []
        text_parts: list[str]       = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(_ToolCall(
                    id        = block.id,
                    name      = block.name,
                    arguments = json.dumps(block.input),
                ))
            elif block.type == "text":
                text_parts.append(block.text)

        msg = _Message(
            tool_calls = tool_calls if tool_calls else None,
            content    = "".join(text_parts) or None,
        )
        return _FakeResponse(choices=[_Choice(message=msg)])

    # ── stream ────────────────────────────────────────────────────────────────

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        system    = _extract_system(messages)
        converted = _convert_messages(messages)
        async with self._client.messages.stream(
            model     = self.model,
            max_tokens= 4096,
            system    = system,
            messages  = converted,
        ) as s:
            async for text in s.text_stream:
                yield text

    # ── stream_tools ──────────────────────────────────────────────────────────

    async def stream_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> AsyncIterator[str | list[ToolCallRequest]]:
        system    = _extract_system(messages)
        converted = _convert_messages(messages)

        tool_calls_acc: dict[str, dict] = {}   # block_id → {name, arguments}
        current_tool_id: str | None = None

        async with self._client.messages.stream(
            model      = self.model,
            max_tokens = 4096,
            system     = system,
            messages   = converted,
            tools      = _convert_tools(tools),   # type: ignore[arg-type]
        ) as stream:
            async for event in stream:
                etype = getattr(event, "type", None)

                if etype == "content_block_start":
                    cb = getattr(event, "content_block", None)
                    if cb and getattr(cb, "type", None) == "tool_use":
                        current_tool_id = cb.id
                        tool_calls_acc[cb.id] = {"name": cb.name, "arguments": ""}

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        yield delta.text
                    elif dtype == "input_json_delta" and current_tool_id:
                        tool_calls_acc[current_tool_id]["arguments"] += delta.partial_json

                elif etype == "content_block_stop":
                    current_tool_id = None

                elif etype == "message_delta":
                    mdelta = getattr(event, "delta", None)
                    if mdelta and getattr(mdelta, "stop_reason", None) == "tool_use":
                        yield [
                            ToolCallRequest(id=k, name=v["name"], arguments=v["arguments"])
                            for k, v in tool_calls_acc.items()
                        ]
                        return


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_system(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return m.get("content", "")
    return ""


def _convert_tools(openai_tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool schema list → Anthropic tool schema list."""
    out = []
    for t in openai_tools:
        fn = t.get("function", {})
        out.append({
            "name":         fn.get("name", ""),
            "description":  fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _convert_messages(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-format message list → Anthropic format.

    Key differences:
    - No system role (handled separately)
    - role=tool → role=user with content=[{type:tool_result,...}]
    - assistant turn with tool_calls → content=[{type:tool_use,...}]
    - Consecutive user turns (multiple tool results) must be merged
    """
    raw: list[dict] = []
    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            continue
        if role == "tool":
            raw.append({
                "role": "user",
                "content": [{
                    "type":        "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content":     msg.get("content", ""),
                }],
            })
        elif role == "assistant" and msg.get("tool_calls"):
            blocks = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                fn   = tc.get("function", {})
                args = fn.get("arguments", "{}")
                blocks.append({
                    "type":  "tool_use",
                    "id":    tc.get("id", ""),
                    "name":  fn.get("name", ""),
                    "input": json.loads(args) if isinstance(args, str) else args,
                })
            raw.append({"role": "assistant", "content": blocks})
        else:
            # Content may be a plain string or a list of content blocks
            # (the latter when the user attached an image via vision path).
            content = msg.get("content", "")
            if isinstance(content, list):
                # Convert OpenAI-style content block list → Anthropic format.
                ant_blocks: list[dict] = []
                for block in content:
                    if isinstance(block, str):
                        ant_blocks.append({"type": "text", "text": block})
                    elif block.get("type") == "text":
                        ant_blocks.append({"type": "text", "text": block.get("text", "")})
                    elif block.get("type") == "image_url":
                        # OpenAI: {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}
                        # Anthropic: {"type":"image","source":{"type":"base64","media_type":...,"data":...}}
                        url = block.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            # Parse "data:<media_type>;base64,<data>"
                            header, b64data = url.split(",", 1)
                            media_type = header.split(";")[0].split(":", 1)[1]
                            ant_blocks.append({
                                "type": "image",
                                "source": {
                                    "type":       "base64",
                                    "media_type": media_type,
                                    "data":        b64data,
                                },
                            })
                        else:
                            # URL-referenced image — pass as-is (Anthropic supports url source).
                            ant_blocks.append({
                                "type": "image",
                                "source": {"type": "url", "url": url},
                            })
                    else:
                        # Unknown block type — skip silently.
                        pass
                raw.append({"role": role, "content": ant_blocks})
            else:
                raw.append({"role": role, "content": content})

    # Merge consecutive user turns (Anthropic rejects two user turns in a row)
    merged: list[dict] = []
    for turn in raw:
        if (
            merged
            and merged[-1]["role"] == "user"
            and turn["role"] == "user"
            and isinstance(merged[-1].get("content"), list)
            and isinstance(turn.get("content"), list)
        ):
            merged[-1]["content"].extend(turn["content"])
        else:
            merged.append(turn)
    return merged
