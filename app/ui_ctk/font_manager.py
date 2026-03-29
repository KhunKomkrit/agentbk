"""Font manager — Thai-compatible font name resolution for tkinter."""
from __future__ import annotations

import os
import tkinter.font as tkfont
from functools import lru_cache

# macOS Thai font preference chain (name as tkinter knows them)
_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc",
    "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",
    "/System/Library/Fonts/Supplemental/Silom.ttf",
    "/System/Library/Fonts/ThonburiUI.ttc",
    os.path.join(os.path.dirname(__file__), "../assets/fonts/NotoSansThai-Regular.ttf"),
]

# tkinter family names for the same fonts (checked against font.families())
_THAI_FAMILY_CANDIDATES = [
    "SukhumvitSet",
    "Ayuthaya",
    "Silom",
    "Thonburi",
    "Noto Sans Thai",
]

_resolved_family: str | None = None


def resolve_family() -> str:
    """Return first available Thai font family name (tkinter-compatible)."""
    global _resolved_family
    if _resolved_family is not None:
        return _resolved_family

    try:
        available = set(tkfont.families())
        for candidate in _THAI_FAMILY_CANDIDATES:
            if candidate in available:
                _resolved_family = candidate
                return _resolved_family
    except Exception:
        pass

    # Last resort — check file path exists and use file loading via PIL (not tkinter)
    for path in _FONT_PATHS:
        if os.path.exists(path):
            # tkinter can't load .ttf/.ttc directly by path — use Ayuthaya fallback name
            break

    _resolved_family = "Arial"
    return _resolved_family


@lru_cache(maxsize=64)
def get(size: int, bold: bool = False) -> tuple[str, int, str]:
    """Return (family, size, weight) tuple suitable for CTk font= argument."""
    family = resolve_family()
    weight = "bold" if bold else "normal"
    return (family, size, weight)


def ctk_font(size: int, bold: bool = False):
    """Return a customtkinter CTkFont instance."""
    import customtkinter as ctk  # local import — ctk not imported at module level
    family = resolve_family()
    return ctk.CTkFont(family=family, size=size, weight="bold" if bold else "normal")
