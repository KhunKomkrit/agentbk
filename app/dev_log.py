"""Dev-mode logger — active only when DEV=1 env var is set.

Usage:
    DEV=1 uv run python -m app.main

All output goes to stderr so it doesn't mix with app stdout.
"""
from __future__ import annotations
import os
import sys
import time
import threading

_ENABLED: bool = os.getenv("DEV", "0").strip() == "1"
_T0: float = time.perf_counter()
_LOCK = threading.Lock()

# ANSI colours (disabled on Windows without ANSI support)
_C = {
    "reset":  "\033[0m",
    "grey":   "\033[90m",
    "cyan":   "\033[96m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "blue":   "\033[94m",
    "bold":   "\033[1m",
}

_TAG_COLOR = {
    "BOOT":   "cyan",
    "MCP":    "blue",
    "RAG":    "green",
    "LLM":    "yellow",
    "TOOL":   "yellow",
    "TIMING": "green",
    "WARN":   "red",
    "INFO":   "grey",
}


def log(tag: str, msg: str, *, elapsed: float | None = None) -> None:
    """Emit a dev log line. No-op when DEV != 1."""
    if not _ENABLED:
        return
    now = time.perf_counter() - _T0
    col = _C.get(_TAG_COLOR.get(tag, "grey"), "")
    rst = _C["reset"]
    grey = _C["grey"]
    elapsed_str = f"  {grey}(+{elapsed*1000:.0f}ms){rst}" if elapsed is not None else ""
    line = f"{grey}[{now:7.2f}s]{rst} {col}[{tag}]{rst} {msg}{elapsed_str}\n"
    with _LOCK:
        sys.stderr.write(line)
        sys.stderr.flush()


def enabled() -> bool:
    return _ENABLED


def banner() -> None:
    """Print startup banner when DEV=1."""
    if not _ENABLED:
        return
    b = _C["bold"]
    c = _C["cyan"]
    r = _C["reset"]
    sys.stderr.write(
        f"\n{b}{c}{'─'*52}{r}\n"
        f"{b}{c}  AgentBK  DEV MODE  (DEV=1){r}\n"
        f"{b}{c}  Logging: router · RAG · MCP · timing{r}\n"
        f"{b}{c}{'─'*52}{r}\n\n"
    )
    sys.stderr.flush()
