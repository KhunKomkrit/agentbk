"""TTS speaker — edge-tts (optional) > macOS say > silent fallback."""
from __future__ import annotations
import os
import queue
import subprocess
import threading
from typing import Callable


class TTSSpeaker:
    """Serialised TTS queue. speak() is non-blocking; audio plays in worker thread."""

    def __init__(
        self,
        on_start: Callable | None = None,
        on_done:  Callable | None = None,
    ) -> None:
        self._queue:    queue.Queue[str | None] = queue.Queue()
        self._on_start  = on_start
        self._on_done   = on_done
        self._backend   = _detect_backend()
        self._worker    = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def speak(self, text: str) -> None:
        """Enqueue text for TTS. Returns immediately."""
        if text.strip():
            self._queue.put(text)

    def stop(self) -> None:
        """Clear queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _run(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                break
            if self._on_start:
                self._on_start()
            try:
                self._backend(text)
            except Exception:
                pass
            if self._on_done:
                self._on_done()


# ── backend detection ─────────────────────────────────────────────────────────

def _detect_backend() -> Callable[[str], None]:
    try:
        import edge_tts  # noqa: F401
        return _edge_tts_backend
    except ImportError:
        pass
    if _say_available():
        return _say_backend
    return lambda text: None   # silent


def _say_available() -> bool:
    try:
        return subprocess.run(["which", "say"], capture_output=True).returncode == 0
    except OSError:
        return False


def _say_backend(text: str) -> None:
    voice = os.getenv("TTS_SAY_VOICE", "")
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    subprocess.run(cmd, capture_output=True)


def _edge_tts_backend(text: str) -> None:
    import asyncio
    asyncio.run(_edge_tts_async(text))


async def _edge_tts_async(text: str) -> None:
    import io
    import edge_tts
    import pygame

    is_thai = any("\u0e00" <= ch <= "\u0e7f" for ch in text)
    voice   = "th-TH-PremwadeeNeural" if is_thai else "en-US-AriaNeural"
    communicate = edge_tts.Communicate(text=text, voice=voice)

    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    audio_bytes = buf.getvalue()
    if not audio_bytes:
        return

    # Play via pygame mixer if available
    if pygame.mixer.get_init():
        buf.seek(0)
        try:
            pygame.mixer.music.load(buf)
            pygame.mixer.music.play()
            import time
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            return
        except Exception:
            pass

    # Fallback: write to temp file and play with afplay (macOS)
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        subprocess.run(["afplay", tmp], capture_output=True)
    finally:
        os.unlink(tmp)
