"""OllamaManager — auto-start Ollama and pull models if missing.

Strategy (Tier 1):
  1. Check if Ollama is already listening on :11434
  2. If not: find `ollama` binary in PATH / common locations
  3. If found: launch `ollama serve` as a subprocess, wait up to 10 s
  4. If not found: return False (caller shows install prompt)
  5. Check if the desired model exists; if not: pull it with progress callback
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from typing import Callable

import httpx

# Ollama default endpoint
_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

# Small model good at tool-calling, ~2 GB on disk
DEFAULT_MODEL = "qwen2.5:3b"

# Common binary locations per platform
_COMMON_PATHS: list[str] = [
    "/usr/local/bin/ollama",
    "/usr/bin/ollama",
    os.path.expanduser("~/.ollama/bin/ollama"),
]
if sys.platform == "win32":
    _COMMON_PATHS += [
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Ollama", "ollama.exe"),
    ]


def is_running(timeout: float = 1.5) -> bool:
    """Return True if Ollama HTTP server is reachable."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"{_BASE}/")
            return r.status_code < 500
    except Exception:
        return False


def find_binary() -> str | None:
    """Return path to `ollama` binary, or None if not found."""
    found = shutil.which("ollama")
    if found:
        return found
    for p in _COMMON_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def launch(timeout: float = 12.0) -> bool:
    """Start `ollama serve` as a detached subprocess.

    Returns True when the server is accepting connections, False if timed out.
    """
    binary = find_binary()
    if not binary:
        return False

    # Detach from current process group so it survives AgentBK restarts
    kwargs: dict = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        subprocess.Popen(
            [binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
    except OSError:
        return False

    # Poll until ready
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running(timeout=0.5):
            return True
        time.sleep(0.5)
    return False


def list_models() -> list[str]:
    """Return names of locally available models (e.g. ['llama3:latest', 'qwen2.5:3b'])."""
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{_BASE}/api/tags")
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def has_model(name: str) -> bool:
    """Return True if `name` (or `name:latest`) is already pulled."""
    models = list_models()
    clean = name if ":" in name else f"{name}:latest"
    return any(m == clean or m == name for m in models)


def pull_model(
    name: str,
    progress_cb: Callable[[str, float], None] | None = None,
) -> bool:
    """Pull `name` from Ollama registry.

    progress_cb(status_text, fraction_0_to_1) called periodically.
    Returns True on success.
    """
    binary = find_binary()
    if not binary:
        return False

    import json as _json

    try:
        proc = subprocess.Popen(
            [binary, "pull", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.stdout is None:
            return False

        # `ollama pull` prints JSON-lines with {"status":"...","completed":N,"total":N}
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = _json.loads(line)
                status = obj.get("status", "")
                completed = obj.get("completed", 0)
                total = obj.get("total", 0)
                frac = (completed / total) if total > 0 else 0.0
                if progress_cb:
                    progress_cb(status, frac)
            except _json.JSONDecodeError:
                # plain text line from older Ollama versions
                if progress_cb:
                    progress_cb(line, 0.0)

        proc.wait()
        return proc.returncode == 0

    except Exception:
        return False


def ensure_ready(
    model: str = DEFAULT_MODEL,
    progress_cb: Callable[[str, float], None] | None = None,
) -> tuple[bool, str]:
    """Full preflight: ensure Ollama is running and `model` is available.

    Returns (success, message).
    progress_cb(text, fraction) is called throughout.
    """
    def _cb(text: str, frac: float = 0.0) -> None:
        if progress_cb:
            progress_cb(text, frac)

    # 1. Check if already running
    if not is_running():
        _cb("Starting Ollama…", 0.0)
        if not launch():
            binary = find_binary()
            if not binary:
                return False, "Ollama not found. Install from https://ollama.com"
            return False, "Ollama failed to start within timeout"
    _cb("Ollama running ✓", 1.0)

    # 2. Check model
    if not has_model(model):
        _cb(f"Downloading {model}… (first run only)", 0.0)

        def _pull_cb(status: str, frac: float) -> None:
            # Show percentage only when we have real progress
            if frac > 0:
                _cb(f"{status} {int(frac * 100)}%", frac)
            else:
                _cb(status, 0.0)

        ok = pull_model(model, _pull_cb)
        if not ok:
            return False, f"Failed to pull {model}"
        _cb(f"{model} ready ✓", 1.0)
    else:
        _cb(f"{model} ready ✓", 1.0)

    return True, "OK"
