"""AgentRouter — memory + tool loop + MCP + TTS + streaming queue."""
from __future__ import annotations
import asyncio
import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Literal

from app.providers.base import BaseLLMProvider
from app.agent.memory import ConversationMemory
from app.agent.tools import TOOL_SCHEMAS, execute_tool
from app import dev_log

_SYSTEM_PROMPT = (
    "You are AgentBK, a helpful desktop AI assistant. "
    "Be concise and friendly. Support both Thai and English naturally."
)
_MAX_TOOL_ROUNDS = 5

# Keywords that suggest the user wants a tool (date/time, math, weather).
# Anything else uses fast plain-stream path (no tool schemas → ~3× faster TTFT).
_TOOL_WORDS: frozenset[str] = frozenset({
    # time / date
    "time", "date", "today", "now", "datetime", "clock", "day", "month", "year",
    "เวลา", "วันที่", "วันนี้", "ตอนนี้", "นาฬิกา",
    # math
    "calculate", "compute", "math", "sum", "total", "average", "equation",
    "คำนวณ", "บวก", "ลบ", "คูณ", "หาร", "เท่ากับ",
    # weather
    "weather", "forecast", "temperature", "rain", "sunny", "humid", "wind",
    "อากาศ", "พยากรณ์", "ฝน", "ร้อน", "หนาว", "ลม", "ความชื้น",
})


def _wants_tools(text: str) -> bool:
    """Heuristic: does this message likely need a tool call?"""
    lower = text.lower()
    return any(w in lower for w in _TOOL_WORDS)


@dataclass
class _Chunk:
    kind: Literal["chunk", "done", "error", "tool_use", "init_progress", "ollama_progress"]
    text: str = ""


def _load_provider() -> BaseLLMProvider:
    name = os.getenv("ACTIVE_PROVIDER", "ollama").lower()
    if name == "anthropic":
        from app.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "openai":
        from app.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    from app.providers.ollama_provider import OllamaProvider
    return OllamaProvider()


class AgentRouter:
    def __init__(self) -> None:
        self._provider: BaseLLMProvider = _load_provider()
        self._memory = ConversationMemory()
        self.result_queue: queue.SimpleQueue[_Chunk] = queue.SimpleQueue()
        self.is_ready = False  # True when all background init is done
        self._init_steps_done = 0
        self._init_steps_total = 4  # Ollama + MCP + LLM warmup + RAG
        dev_log.log("BOOT", f"provider={type(self._provider).__name__}  history={len(self._memory.messages)} msgs")

        # TTS speaker (lazy import so startup doesn't fail if edge-tts absent)
        from app.tts.speaker import TTSSpeaker
        self.speaker = TTSSpeaker()

        # Ollama preflight — auto-start server and pull model if needed
        # Runs in background so UI can show progress immediately
        self._ollama_ok = False
        self._ollama_ready_event = threading.Event()  # signals _warmup to proceed
        threading.Thread(target=self._preflight_ollama, daemon=True).start()

        # MCP clients — one per enabled server in mcp_servers.json
        self._mcps: list = []
        self._init_mcps()

        # RAG knowledge base store (lazy import — heavy deps)
        self._rag_store = None
        self._rag_ready = False   # True once embedder is loaded in background
        try:
            from app.rag.store import RAGStore
            self._rag_store = RAGStore()
            dev_log.log("BOOT", f"RAGStore ready  docs={self._rag_store.list_documents().__len__()}")
        except Exception as e:
            dev_log.log("WARN", f"RAGStore unavailable: {e}")

        # Warm up the LLM's KV cache in background so the first real message
        # benefits from a pre-loaded system-prompt context.
        threading.Thread(target=self._warmup, daemon=True).start()

        # Pre-load the sentence-transformers embedder in background so RAG search
        # never blocks a response. _rag_ready guards _async_stream from calling
        # embed() before the model is warm.
        if self._rag_store:
            threading.Thread(target=self._warmup_rag, daemon=True).start()
        else:
            self._mark_init_step_done("RAG")  # skip if unavailable

    # ── public ────────────────────────────────────────────────────────────────

    def start_stream(self, user_text: str, attachment=None) -> None:
        """Begin an LLM stream, optionally with a file/image attachment.

        ``attachment`` is an ``AttachmentResult`` (from app.agent.attachment).
        - image + provider supports_vision → content list with text + image_url block
        - image + no vision support → plain text with a notice appended
        - pdf / text → extracted content appended to user message as text
        """
        content: str | list

        if attachment is None:
            content = user_text
        elif attachment.kind == "image":
            if self._provider.supports_vision and attachment.image_b64:
                # Build OpenAI-style multimodal content list.
                # Anthropic provider converts this in _convert_messages().
                data_url = f"data:{attachment.media_type};base64,{attachment.image_b64}"
                content = [
                    {"type": "text", "text": user_text or "อธิบายรูปนี้ให้หน่อย"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]
            else:
                # Text-only model — just tell the user it's not supported.
                notice = (
                    f"\n\n[แนบรูป: {attachment.filename}]\n"
                    f"⚠ model ที่ใช้งานอยู่ ({self._provider.model}) ไม่รองรับ vision\n"
                    f"เปลี่ยนไปใช้ Anthropic (Claude) หรือ Ollama vision model เช่น llava, qwen2-vl"
                )
                content = (user_text + notice) if user_text else notice.strip()
        else:
            # PDF or text — inject extracted content as context.
            file_block = (
                f"\n\n---\nไฟล์แนบ: {attachment.filename}\n"
                f"{attachment.text_content}\n---"
            )
            content = (user_text + file_block) if user_text else file_block.strip()

        # Store normalised content in memory.
        # json.dumps handles both str and list[dict] correctly.
        self._memory.add("user", content)
        dev_log.log("ATTACH", f"kind={attachment.kind if attachment else 'none'}  "
                               f"vision={self._provider.supports_vision}")
        threading.Thread(target=self._run_stream, daemon=True).start()

    def drain(self, max_items: int = 20) -> list[_Chunk]:
        items: list[_Chunk] = []
        try:
            for _ in range(max_items):
                items.append(self.result_queue.get_nowait())
        except queue.Empty:
            pass
        return items

    def clear_history(self) -> None:
        self._memory.clear()
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

    def reload_mcp(self) -> None:
        """Re-connect MCP servers after settings change. Safe to call from main thread."""
        self._mcps = []
        self._init_mcps()

    @property
    def last_assistant_message(self) -> str:
        for msg in reversed(self._memory.messages):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""

    # ── internal ──────────────────────────────────────────────────────────────

    def _init_mcps(self) -> None:
        """Load enabled MCP servers from config and connect each in a background thread.

        Supports two server types:
          HTTP  — ``{"url": "http://…", "headers": {…}}``
          Stdio — ``{"type": "stdio", "command": "uvx", "args": […], "env": {…}}``
        """
        from app.agent.mcp_config import load_servers
        from app.agent.mcp_client import MCPClient

        servers = load_servers()

        def _is_enabled(s: dict) -> bool:
            if not s.get("enabled", True):
                return False
            if s.get("type") == "stdio":
                return bool(s.get("command", "").strip())
            return bool(s.get("url", "").strip())

        enabled = [s for s in servers if _is_enabled(s)]
        dev_log.log("MCP", f"config: {len(servers)} servers, {len(enabled)} enabled")

        if not enabled:
            self._mark_init_step_done("MCP")
            return

        pending = len(enabled)
        lock = threading.Lock()

        for srv in enabled:
            transport = srv.get("type", "http")  # "http" | "stdio"
            name = srv.get("name", srv.get("url") or srv.get("command", ""))

            if transport == "stdio":
                client = MCPClient(
                    name=name,
                    transport="stdio",
                    command=srv.get("command", ""),
                    args=srv.get("args") or [],
                    env=srv.get("env") or {},
                )
                desc = f"{srv.get('command', '')} {' '.join(srv.get('args') or [])}"
            else:
                client = MCPClient(
                    name=name,
                    headers=srv.get("headers") or {},
                )
                desc = srv.get("url", "")

            self._mcps.append(client)
            dev_log.log("MCP", f"connecting → {name}  {desc}")

            def _connect(c=client, n=name, t=transport, u=srv.get("url", "")):
                nonlocal pending
                t0 = time.perf_counter()
                if t == "stdio":
                    asyncio.run(c.connect_stdio())
                else:
                    asyncio.run(c.connect(u))
                elapsed = time.perf_counter() - t0
                tools_n = len(c.tools)
                if tools_n:
                    dev_log.log("MCP", f"✓ {n}  {tools_n} tools", elapsed=elapsed)
                else:
                    dev_log.log("MCP", f"✗ {n}  unreachable or 0 tools", elapsed=elapsed)
                with lock:
                    pending -= 1
                    if pending == 0:
                        self._mark_init_step_done("MCP")

            threading.Thread(target=_connect, daemon=True).start()

    def _warmup_rag(self) -> None:
        """Pre-load the sentence-transformers embedder so RAG never blocks a response.

        Init step is marked done immediately so the UI is not blocked waiting for
        the embedder. _rag_ready flag gates actual RAG usage once the model is warm.
        """
        self._mark_init_step_done("RAG")   # unblock UI right away
        dev_log.log("RAG", "loading embedder in background…")
        t0 = time.perf_counter()

        def _load() -> None:
            try:
                from app.rag.embedder import get_embedder
                get_embedder()
                self._rag_ready = True
                dev_log.log("RAG", "embedder ready ✓", elapsed=time.perf_counter() - t0)
            except Exception as e:
                dev_log.log("WARN", f"embedder load failed: {e}", elapsed=time.perf_counter() - t0)

        threading.Thread(target=_load, daemon=True).start()

    def _warmup(self) -> None:
        """Pre-warm the provider's KV cache with the system prompt."""
        # Wait for Ollama preflight to finish before trying to stream
        # (prevents hanging when Ollama is still starting up or pulling model)
        self._ollama_ready_event.wait(timeout=180.0)
        dev_log.log("LLM", "KV-cache warmup starting…")
        t0 = time.perf_counter()
        async def _do():
            try:
                warmup_msgs = [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": "hi"},
                ]
                # Use wait_for to prevent hanging forever on unresponsive provider
                async def _stream_one():
                    async for _ in self._provider.stream(warmup_msgs):
                        break
                await asyncio.wait_for(_stream_one(), timeout=30.0)
                dev_log.log("LLM", "KV-cache warm ✓", elapsed=time.perf_counter() - t0)
            except asyncio.TimeoutError:
                dev_log.log("WARN", "warmup timed out (30s)", elapsed=time.perf_counter() - t0)
            except Exception as e:
                dev_log.log("WARN", f"warmup failed: {e}", elapsed=time.perf_counter() - t0)
        asyncio.run(_do())
        self._mark_init_step_done("LLM")

    def _preflight_ollama(self) -> None:
        """Ensure Ollama is running and default model is pulled (Ollama provider only)."""
        provider_name = os.getenv("ACTIVE_PROVIDER", "ollama").lower()
        if provider_name != "ollama":
            self._mark_init_step_done("Ollama")  # skip for cloud providers
            return

        from app.agent.ollama_manager import ensure_ready, DEFAULT_MODEL
        model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

        def _progress(text: str, frac: float) -> None:
            self.result_queue.put(_Chunk(kind="ollama_progress", text=text))
            dev_log.log("OLLAMA", text)

        ok, msg = ensure_ready(model=model, progress_cb=_progress)
        self._ollama_ok = ok
        if not ok:
            dev_log.log("WARN", f"Ollama preflight failed: {msg}")
            self.result_queue.put(_Chunk(kind="ollama_progress", text=f"⚠ {msg}"))
        self._ollama_ready_event.set()  # unblock _warmup regardless of success
        self._mark_init_step_done("Ollama")

    def _mark_init_step_done(self, step_name: str) -> None:
        """Mark an initialization step as complete and notify UI."""
        self._init_steps_done += 1
        # Set is_ready BEFORE putting chunk on queue so UI sees it as True
        # when it drains the final init_progress chunk (avoids race condition).
        if self._init_steps_done >= self._init_steps_total:
            self.is_ready = True
            dev_log.log("BOOT", "All systems ready ✓")
        progress_text = f"{step_name} ready ({self._init_steps_done}/{self._init_steps_total})"
        self.result_queue.put(_Chunk(kind="init_progress", text=progress_text))
    
    def _run_stream(self) -> None:
        asyncio.run(self._async_stream())

    async def _async_stream(self) -> None:
        t_start = time.perf_counter()

        # Build system prompt, optionally augmented with RAG context.
        # last_user_content may be a list (multimodal) — extract text part for RAG/logging.
        last_user_content = next(
            (m.get("content", "") for m in reversed(self._memory.messages)
             if m.get("role") == "user"),
            "",
        )
        # Flatten multimodal content to a plain string for RAG search and logging.
        last_user = (
            " ".join(b.get("text", "") for b in last_user_content if isinstance(b, dict))
            if isinstance(last_user_content, list)
            else last_user_content
        )
        dev_log.log("LLM", f"user={last_user[:60]!r}  history={len(self._memory.messages)} msgs")

        system = _SYSTEM_PROMPT
        if self._rag_store and self._rag_ready and last_user:
            try:
                t_rag = time.perf_counter()
                hits = self._rag_store.search(last_user, k=4)
                if hits:
                    rag_block = (
                        "\n\n---\nRelevant context from knowledge base:\n"
                        + "\n---\n".join(hits)
                    )
                    system = _SYSTEM_PROMPT + rag_block
                dev_log.log("RAG", f"search → {len(hits)} hits", elapsed=time.perf_counter() - t_rag)
            except Exception as e:
                dev_log.log("WARN", f"RAG search failed: {e}")
        elif not self._rag_ready:
            dev_log.log("RAG", "skipped (embedder warming up)")

        messages: list[dict] = (
            [{"role": "system", "content": system}]
            + self._memory.messages
        )

        # Decide whether this message needs tool calling.
        # Passing tool schemas to Ollama adds ~2s of TTFT even when no tool is used.
        mcp_tools = [t for c in self._mcps for t in c.tools]
        all_tools = list(TOOL_SCHEMAS) + mcp_tools

        # If MCP servers are connected, always use the tool path —
        # the user added them explicitly so they should always be available.
        # For built-in tools only, use keyword heuristic to avoid TTFT penalty.
        if mcp_tools:
            use_tools = True
        else:
            use_tools = bool(all_tools) and _wants_tools(last_user)
        path = "tool" if use_tools else "fast"
        dev_log.log("LLM", f"path={path}  tools_available={len(all_tools)}  mcp_tools={len(mcp_tools)}")

        full = ""
        t_first_chunk: float | None = None
        try:
            if not use_tools:
                # ── Fast path: plain streaming, no tool schemas ────────────────
                async for chunk in self._provider.stream(messages):
                    if t_first_chunk is None:
                        t_first_chunk = time.perf_counter()
                        dev_log.log("TIMING", f"TTFT={t_first_chunk - t_start:.3f}s")
                    full += chunk
                    self.result_queue.put(_Chunk(kind="chunk", text=chunk))
                self.result_queue.put(_Chunk(kind="done"))

            else:
                # ── Tool path: stream_tools() loop ────────────────────────────
                for round_n in range(_MAX_TOOL_ROUNDS + 1):
                    tool_requests = None
                    round_text    = ""

                    async for item in self._provider.stream_tools(messages, all_tools):
                        if isinstance(item, list):
                            tool_requests = item
                        else:
                            if t_first_chunk is None:
                                t_first_chunk = time.perf_counter()
                                dev_log.log("TIMING", f"TTFT={t_first_chunk - t_start:.3f}s  (round {round_n})")
                            round_text += item
                            full       += item
                            self.result_queue.put(_Chunk(kind="chunk", text=item))

                    if tool_requests is None:
                        self.result_queue.put(_Chunk(kind="done"))
                        break

                    dev_log.log("TOOL", f"round {round_n}: {[tc.name for tc in tool_requests]}")
                    messages.append({
                        "role":       "assistant",
                        "content":    round_text,
                        "tool_calls": [
                            {
                                "id":       tc.id,
                                "type":     "function",
                                "function": {
                                    "name":      tc.name,
                                    "arguments": tc.arguments,
                                },
                            }
                            for tc in tool_requests
                        ],
                    })

                    for tc in tool_requests:
                        self.result_queue.put(_Chunk(kind="tool_use", text=tc.name))
                        try:
                            args = json.loads(tc.arguments or "{}")
                            dispatched = False
                            for _client in self._mcps:
                                if _client.owns(tc.name):
                                    t_tool = time.perf_counter()
                                    result = await _client.call_tool(tc.name, args)
                                    dev_log.log("TOOL", f"MCP:{tc.name} → {result[:60]!r}", elapsed=time.perf_counter() - t_tool)
                                    dispatched = True
                                    break
                            if not dispatched:
                                t_tool = time.perf_counter()
                                result = await execute_tool(tc.name, args)
                                dev_log.log("TOOL", f"local:{tc.name} → {result[:60]!r}", elapsed=time.perf_counter() - t_tool)
                        except Exception as exc:
                            result = f"Tool error: {exc}"
                            dev_log.log("WARN", f"tool {tc.name} error: {exc}")
                        messages.append({
                            "role":         "tool",
                            "tool_call_id": tc.id,
                            "name":         tc.name,
                            "content":      result,
                        })
                else:
                    self.result_queue.put(_Chunk(kind="done"))

        except Exception as exc:
            dev_log.log("WARN", f"stream error: {exc}")
            self.result_queue.put(_Chunk(kind="error", text=str(exc)))
        finally:
            t_total = time.perf_counter() - t_start
            dev_log.log("TIMING", f"total={t_total:.3f}s  tokens≈{len(full.split())}")
            if full:
                self._memory.add("assistant", full)
                self._memory.persist()
