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


def _get_mic_permission_status() -> int:
    """Return AVFoundation authorization status (0=notDetermined 1=restricted 2=denied 3=authorized).
    Returns 3 on non-macOS platforms."""
    try:
        import AVFoundation as av  # type: ignore[import]
        return av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeAudio)
    except ImportError:
        return 3


def _request_mic_permission() -> bool:
    """macOS: request microphone permission via AVFoundation dialog.

    Returns True if permission is granted, False if denied.
    On non-macOS platforms always returns True.
    """
    try:
        import AVFoundation as av  # type: ignore[import]
    except ImportError:
        return True  # not macOS or pyobjc not installed — let sounddevice handle it

    status = av.AVCaptureDevice.authorizationStatusForMediaType_(av.AVMediaTypeAudio)
    if status == 3:
        return True
    if status == 2 or status == 1:
        return False

    # status == 0 (notDetermined) — request access; this shows the macOS dialog
    granted_event = threading.Event()
    granted_holder: list[bool] = [False]

    def _handler(granted: bool) -> None:
        granted_holder[0] = granted
        granted_event.set()

    av.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        av.AVMediaTypeAudio, _handler
    )
    granted_event.wait(timeout=30.0)  # wait up to 30 s for user to respond
    return granted_holder[0]


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
        """Open the microphone stream and start collecting audio.

        Permission request and PortAudio reinit run in a background thread so
        the pygame event loop is never blocked.
        """
        if self._is_recording:
            return
        try:
            import sounddevice as sd  # noqa: F401
        except ImportError:
            self.result_queue.put("[ไม่พบ sounddevice — รัน: uv add sounddevice]")
            return

        # Run permission check + stream open in background to avoid blocking main thread
        threading.Thread(target=self._open_stream, daemon=True).start()

    def _open_stream(self) -> None:
        """Background: request permission (if needed) then open the InputStream."""
        import sounddevice as sd

        status = _get_mic_permission_status()
        if status == 2 or status == 1:
            self.result_queue.put("[mic denied: เปิด System Settings › Privacy › Microphone แล้วเพิ่ม Terminal]")
            return
        if status == 0:
            # notDetermined — show dialog (blocks this background thread, not main)
            _request_mic_permission()
            self.result_queue.put("[mic: ได้รับสิทธิ์แล้ว กรุณารีสตาร์ท app เพื่อเปิดใช้งานไมโครโฟน]")
            return

        # status == 3: authorized — reinit PortAudio so it sees the mic
        try:
            sd._terminate()   # type: ignore[attr-defined]
            sd._initialize()  # type: ignore[attr-defined]
        except Exception:
            pass

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
