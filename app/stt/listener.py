"""SpeechListener — sounddevice recording + openai-whisper transcription.

Usage (toggle mode):
    listener = SpeechListener()
    listener.start_recording()        # call from main thread on button press
    listener.stop_and_transcribe(cb)  # call again on second press; cb(text) fires in main thread via queue
"""
from __future__ import annotations

import os
import queue
import threading
from typing import Callable

import numpy as np

# Audio format expected by Whisper
_SAMPLE_RATE = 16_000
_CHANNELS    = 1
_DTYPE       = "float32"

# Whisper model name — override with WHISPER_MODEL env var.
# "small" has good Thai support and runs in ~5s on Apple Silicon.
_DEFAULT_MODEL = "small"


class SpeechListener:
    """Record audio from the default microphone, then transcribe with Whisper.

    Designed for use from a pygame main loop:
    - start_recording() and stop_and_transcribe() may be called from the main thread.
    - Transcription runs in a background daemon thread.
    - Results are delivered via a thread-safe queue; call drain() each frame to
      receive completed transcriptions.
    """

    def __init__(self) -> None:
        self._chunks:      list[np.ndarray] = []
        self._stream       = None          # sounddevice InputStream
        self._is_recording = False
        self._lock         = threading.Lock()
        self._model        = None          # whisper model (lazy-loaded)
        self._model_name   = os.getenv("WHISPER_MODEL", _DEFAULT_MODEL)
        # Completed transcription texts land here; drain in game loop.
        self.result_queue: queue.SimpleQueue[str] = queue.SimpleQueue()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    # ── public API ────────────────────────────────────────────────────────────

    def start_recording(self) -> None:
        """Open the microphone stream and start collecting audio."""
        if self._is_recording:
            return
        try:
            import sounddevice as sd
        except ImportError:
            self.result_queue.put("[ไม่พบ sounddevice — รัน: uv add sounddevice]")
            return

        self._chunks = []
        self._is_recording = True

        def _callback(indata: np.ndarray, frames: int, time, status) -> None:  # noqa: ANN001
            with self._lock:
                self._chunks.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                callback=_callback,
            )
            self._stream.start()
        except Exception as exc:
            self._is_recording = False
            self.result_queue.put(f"[mic error: {exc}]")

    def stop_and_transcribe(self, callback: Callable[[str], None] | None = None) -> None:
        """Stop recording and transcribe in a background thread.

        When done, puts the text into result_queue AND calls callback(text) if provided.
        callback is called from the background thread — use it only to set simple state.
        """
        if not self._is_recording:
            return
        self._is_recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            chunks = list(self._chunks)
        self._chunks = []

        threading.Thread(
            target=self._transcribe,
            args=(chunks, callback),
            daemon=True,
        ).start()

    def drain(self) -> list[str]:
        """Return all completed transcriptions. Call once per frame in game loop."""
        results: list[str] = []
        try:
            while True:
                results.append(self.result_queue.get_nowait())
        except queue.Empty:
            pass
        return results

    # ── internal ─────────────────────────────────────────────────────────────

    def _load_model(self) -> object:
        """Lazy-load Whisper model (heavy — runs only once)."""
        if self._model is None:
            try:
                import whisper
                self._model = whisper.load_model(self._model_name)
            except ImportError:
                raise RuntimeError("openai-whisper ไม่ได้ติดตั้ง — รัน: uv sync")
        return self._model

    def _transcribe(
        self,
        chunks: list[np.ndarray],
        callback: Callable[[str], None] | None,
    ) -> None:
        """Background thread: concatenate audio → whisper → deliver result."""
        if not chunks:
            text = ""
        else:
            try:
                audio = np.concatenate(chunks, axis=0).flatten()
                model = self._load_model()
                # Whisper expects float32 mono at 16 kHz — already in that format.
                result = model.transcribe(audio, fp16=False)
                text = result.get("text", "").strip()
            except Exception as exc:
                text = f"[transcribe error: {exc}]"

        self.result_queue.put(text)
        if callback and text:
            callback(text)
