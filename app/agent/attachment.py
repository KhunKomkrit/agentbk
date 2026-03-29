"""Attachment processor — image, PDF, and text file ingestion for AgentBK chat."""
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Maximum pixels on the long edge before resizing (keeps token cost reasonable).
_MAX_IMAGE_PX = 1024
# Maximum extracted characters from PDF/text (≈ 2 000 tokens at 4 chars/token).
_MAX_TEXT_CHARS = 8_000
# Thumbnail size shown in the preview strip and chat bubbles.
THUMB_SIZE = (48, 48)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_PDF_EXTS   = {".pdf"}

# These media-type strings are what Anthropic / OpenAI vision APIs expect.
_MIME: dict[str, str] = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@dataclass
class AttachmentResult:
    """Processed attachment ready for display and sending to the LLM."""
    kind:         Literal["image", "pdf", "text"]
    filename:     str
    # For PDF and text: the extracted/read content.  Empty for images.
    text_content: str = ""
    # For images: base64-encoded bytes (no header prefix — added at send time).
    image_b64:    str | None = None
    # MIME type, e.g. "image/jpeg".  Set for images only.
    media_type:   str | None = None
    # pygame.Surface (48×48) thumbnail for display; created on the main thread.
    thumb:        object = field(default=None, repr=False)
    # Raw RGB bytes for thumbnail — populated by background thread, converted to
    # thumb (pygame.Surface) on the main thread to avoid SDL2 thread-safety issues.
    thumb_raw:    bytes | None = field(default=None, repr=False)


def process_file(path: str) -> AttachmentResult:
    """Read a file from disk and return an AttachmentResult.

    Supports: PNG/JPG/WEBP images, PDF, and plain text/code files.
    Images are resized to at most _MAX_IMAGE_PX on the long edge.
    PDF and text content is truncated to _MAX_TEXT_CHARS characters.
    """
    p    = Path(path)
    ext  = p.suffix.lower()
    name = p.name

    if ext in _IMAGE_EXTS:
        return _process_image(p, name, ext)
    if ext in _PDF_EXTS:
        return _process_pdf(p, name)
    # Everything else treated as text/code.
    return _process_text(p, name)


def from_clipboard() -> AttachmentResult | None:
    """Try to grab an image from the system clipboard.

    Currently a stub — macOS NSPasteboard access requires PyObjC bridging that
    conflicts with pygame's event loop. Returns None with a notice text so the
    caller can show a toast instead.
    """
    # Future: use AppKit.NSPasteboard on macOS, win32clipboard on Windows.
    return None


def clipboard_unsupported_msg() -> str:
    return "ยังไม่รองรับการวาง (Paste) รูปจาก clipboard — ใช้ Drag & Drop หรือปุ่ม 📎 แทน"


# ── private helpers ───────────────────────────────────────────────────────────

def _process_image(p: Path, name: str, ext: str) -> AttachmentResult:
    from PIL import Image  # Pillow is already a dependency

    with Image.open(p) as img:
        img = img.convert("RGB")
        # Resize so the long edge ≤ _MAX_IMAGE_PX.
        w, h = img.size
        if max(w, h) > _MAX_IMAGE_PX:
            scale = _MAX_IMAGE_PX / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Encode to JPEG for universal compatibility (smaller than PNG for photos).
        buf = io.BytesIO()
        fmt = "PNG" if ext == ".png" else "JPEG"
        save_kwargs: dict = {"format": fmt}
        if fmt == "JPEG":
            save_kwargs["quality"] = 85
        img.save(buf, **save_kwargs)
        b64 = base64.b64encode(buf.getvalue()).decode()

        # Build thumbnail raw bytes (pygame Surface created later on main thread).
        thumb_raw = _pil_to_pygame_thumb(img)

    media_type = _MIME.get(ext, "image/jpeg")
    return AttachmentResult(
        kind       = "image",
        filename   = name,
        image_b64  = b64,
        media_type = media_type,
        thumb_raw  = thumb_raw,
    )


def _process_pdf(p: Path, name: str) -> AttachmentResult:
    try:
        import pypdf  # Already a dependency (used by RAG ingestor)
        reader = pypdf.PdfReader(str(p))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
        full = "\n".join(parts).strip()
    except Exception as exc:
        full = f"[ไม่สามารถ extract PDF ได้: {exc}]"

    truncated = _truncate(full, f"...ข้อความตัดที่ {_MAX_TEXT_CHARS} ตัวอักษร")
    return AttachmentResult(
        kind         = "pdf",
        filename     = name,
        text_content = truncated,
    )


def _process_text(p: Path, name: str) -> AttachmentResult:
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        content = f"[ไม่สามารถอ่านไฟล์ได้: {exc}]"

    truncated = _truncate(content, f"\n...[ตัดที่ {_MAX_TEXT_CHARS} ตัวอักษร]")
    return AttachmentResult(
        kind         = "text",
        filename     = name,
        text_content = truncated,
    )


def _truncate(text: str, suffix: str) -> str:
    if len(text) > _MAX_TEXT_CHARS:
        return text[:_MAX_TEXT_CHARS] + suffix
    return text


def _pil_to_pygame_thumb(img) -> bytes | None:
    """Convert a PIL Image → raw RGB bytes at THUMB_SIZE.

    Returns raw bytes only — the caller must create a pygame.Surface on the
    main thread (SDL2 surface operations are not thread-safe on macOS).
    """
    try:
        from PIL import Image
        thumb_pil = img.copy()
        thumb_pil.thumbnail(THUMB_SIZE, Image.LANCZOS)
        # Pad to exact THUMB_SIZE so layout is predictable.
        canvas = Image.new("RGB", THUMB_SIZE, (30, 32, 52))
        offset = ((THUMB_SIZE[0] - thumb_pil.width) // 2,
                  (THUMB_SIZE[1] - thumb_pil.height) // 2)
        canvas.paste(thumb_pil, offset)
        return canvas.tobytes("raw", "RGB")
    except Exception:
        return None
