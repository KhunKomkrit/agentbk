"""Font manager — Thai-compatible font loading with fallback chain."""

from __future__ import annotations
import os
import pygame

# macOS Thai font candidates (ordered by preference)
_SYSTEM_FONTS = [
    "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc",   # clean modern Thai
    "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",       # classic Thai
    "/System/Library/Fonts/Supplemental/Silom.ttf",          # fallback
    "/System/Library/Fonts/ThonburiUI.ttc",
    # bundled (user-provided)
    os.path.join(os.path.dirname(__file__), "../assets/fonts/NotoSansThai-Regular.ttf"),
]

_cache: dict[int, pygame.font.Font] = {}
_resolved_path: str | None = None


def _resolve_path() -> str | None:
    global _resolved_path
    if _resolved_path is not None:
        return _resolved_path
    for path in _SYSTEM_FONTS:
        if os.path.exists(path):
            _resolved_path = path
            return path
    return None


def get(size: int) -> pygame.font.Font:
    """Return a Thai-capable font at the given pixel size."""
    if size in _cache:
        return _cache[size]
    path = _resolve_path()
    font: pygame.font.Font
    if path:
        try:
            font = pygame.font.Font(path, size)
            _cache[size] = font
            return font
        except Exception:
            pass
    font = pygame.font.SysFont("Arial", size)
    _cache[size] = font
    return font


def get_bold(size: int) -> pygame.font.Font:
    """Bold variant — most Thai system fonts don't have a separate bold face,
    so we synthesise it via pygame's bold flag."""
    key = -size
    if key in _cache:
        return _cache[key]
    path = _resolve_path()
    font: pygame.font.Font
    if path:
        try:
            font = pygame.font.Font(path, size)
            font.bold = True
            _cache[key] = font
            return font
        except Exception:
            pass
    font = pygame.font.SysFont("Arial", size, bold=True)
    _cache[key] = font
    return font
