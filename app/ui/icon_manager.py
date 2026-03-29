"""Icon manager — renders Heroicons SVG files to pygame Surfaces via Pillow.

Falls back to drawing simple shapes if an SVG cannot be parsed.
Supports tinting icons to any RGB colour.
"""
from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import pygame
from PIL import Image, ImageDraw

_ICON_DIR = Path(__file__).parent.parent / "assets" / "icons"
_SVG_NS   = "http://www.w3.org/2000/svg"


# ── SVG path → Pillow rendering (stroke-only, simple d= tokeniser) ────────

def _svg_to_pil(svg_path: Path, size: int) -> Image.Image:
    """Parse a Heroicons-style SVG and rasterise it to a Pillow RGBA image."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Strip namespace for easier tag matching
    def _tag(el: ET.Element) -> str:
        tag = el.tag
        if tag.startswith("{"):
            tag = tag.split("}", 1)[1]
        return tag

    # viewBox of Heroicons is "0 0 24 24"
    vb_str = root.get("viewBox", "0 0 24 24")
    parts  = vb_str.split()
    vb_w, vb_h = float(parts[2]), float(parts[3])
    scale  = size / max(vb_w, vb_h)

    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    stroke_w = max(1, round(1.5 * scale))

    def _parse_d(d: str) -> list[list[tuple[float, float]]]:
        """Return a list of sub-paths, each a list of (x,y) points.
        Handles M,L,H,V,Z,C,S,A (and lowercase relative variants).
        Arc (A) is approximated as a straight line to the endpoint.
        """
        import re
        # tokenise: command letters OR numbers (including negative/scientific)
        tok_re = re.compile(
            r"([MmLlHhVvZzCcSsAaQqTt])"
            r"|([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
        )
        tokens = [m.group(0) for m in tok_re.finditer(d)]

        subpaths: list[list[tuple[float, float]]] = []
        cur_path: list[tuple[float, float]] = []
        start_x, start_y = 0.0, 0.0
        cx, cy = 0.0, 0.0
        last_cp_x, last_cp_y = 0.0, 0.0   # last control point for S/s
        cmd   = "M"
        i     = 0

        def _num() -> float:
            nonlocal i
            v = float(tokens[i]); i += 1; return v

        def _push(x: float, y: float) -> None:
            nonlocal cx, cy
            cx, cy = x, y
            cur_path.append((cx, cy))

        while i < len(tokens):
            t = tokens[i]
            if t.isalpha():
                prev_cmd = cmd
                cmd = t
                i += 1
                # M/m implicitly become L/l after first coord pair
                if cmd == "M": cmd = "M_first"
                elif cmd == "m": cmd = "m_first"
                continue

            # ── coordinate parsing per command ───────────────────────────
            if cmd in ("M_first", "M"):
                x, y = _num(), _num()
                if cmd == "m_first":
                    x += cx; y += cy
                if cmd in ("M_first", "m_first"):
                    if cur_path:
                        subpaths.append(cur_path)
                    cur_path = []
                    start_x, start_y = x, y
                    cmd = "L" if cmd == "M_first" else "l"
                _push(x, y)
            elif cmd == "m_first":
                x, y = _num(), _num()
                x += cx; y += cy
                if cur_path:
                    subpaths.append(cur_path)
                cur_path = []
                start_x, start_y = x, y
                cmd = "l"
                _push(x, y)
            elif cmd in ("L", "l"):
                x, y = _num(), _num()
                if cmd == "l": x += cx; y += cy
                _push(x, y)
            elif cmd in ("H", "h"):
                x = _num()
                if cmd == "h": x += cx
                _push(x, cy)
            elif cmd in ("V", "v"):
                y = _num()
                if cmd == "v": y += cy
                _push(cx, y)
            elif cmd in ("Z", "z"):
                _push(start_x, start_y)
                subpaths.append(cur_path)
                cur_path = []
                i -= 1; i += 1   # no-op, just consume
            elif cmd in ("C", "c"):
                x1, y1 = _num(), _num()
                x2, y2 = _num(), _num()
                x,  y  = _num(), _num()
                if cmd == "c":
                    x1 += cx; y1 += cy
                    x2 += cx; y2 += cy
                    x  += cx; y  += cy
                last_cp_x, last_cp_y = x2, y2
                for s in range(1, 9):
                    t_ = s / 8; mt = 1 - t_
                    bx = mt**3*cx + 3*mt**2*t_*x1 + 3*mt*t_**2*x2 + t_**3*x
                    by = mt**3*cy + 3*mt**2*t_*y1 + 3*mt*t_**2*y2 + t_**3*y
                    cur_path.append((bx, by))
                cx, cy = x, y
            elif cmd in ("S", "s"):
                # Reflect last control point
                x2, y2 = _num(), _num()
                x,  y  = _num(), _num()
                if cmd == "s":
                    x2 += cx; y2 += cy
                    x  += cx; y  += cy
                rx1 = 2*cx - last_cp_x
                ry1 = 2*cy - last_cp_y
                last_cp_x, last_cp_y = x2, y2
                for s in range(1, 9):
                    t_ = s / 8; mt = 1 - t_
                    bx = mt**3*cx + 3*mt**2*t_*rx1 + 3*mt*t_**2*x2 + t_**3*x
                    by = mt**3*cy + 3*mt**2*t_*ry1 + 3*mt*t_**2*y2 + t_**3*y
                    cur_path.append((bx, by))
                cx, cy = x, y
            elif cmd in ("A", "a"):
                # Arc: rx ry x-rot large-arc-flag sweep-flag x y
                _num(); _num(); _num(); _num(); _num()   # skip rx ry rot flags
                x, y = _num(), _num()
                if cmd == "a": x += cx; y += cy
                _push(x, y)   # approximate as line to endpoint
            elif cmd in ("Q", "q"):
                # Quadratic Bézier
                x1, y1 = _num(), _num()
                x,  y  = _num(), _num()
                if cmd == "q":
                    x1 += cx; y1 += cy
                    x  += cx; y  += cy
                for s in range(1, 7):
                    t_ = s / 6; mt = 1 - t_
                    bx = mt**2*cx + 2*mt*t_*x1 + t_**2*x
                    by = mt**2*cy + 2*mt*t_*y1 + t_**2*y
                    cur_path.append((bx, by))
                cx, cy = x, y
            elif cmd in ("T", "t"):
                x, y = _num(), _num()
                if cmd == "t": x += cx; y += cy
                _push(x, y)
            else:
                i += 1  # skip unknown

        if cur_path:
            subpaths.append(cur_path)
        return subpaths

    def _draw_element(el: ET.Element) -> None:
        tag = _tag(el)
        if tag == "path":
            d = el.get("d", "")
            for pts in _parse_d(d):
                if len(pts) >= 2:
                    scaled = [(x * scale, y * scale) for x, y in pts]
                    draw.line(scaled, fill=(255, 255, 255, 255), width=stroke_w)
        elif tag == "circle":
            cx_ = float(el.get("cx", 0)) * scale
            cy_ = float(el.get("cy", 0)) * scale
            r_  = float(el.get("r",  0)) * scale
            draw.ellipse([cx_ - r_, cy_ - r_, cx_ + r_, cy_ + r_],
                         outline=(255, 255, 255, 255), width=stroke_w)
        elif tag == "rect":
            x_  = float(el.get("x", 0)) * scale
            y_  = float(el.get("y", 0)) * scale
            w_  = float(el.get("width",  0)) * scale
            h_  = float(el.get("height", 0)) * scale
            draw.rectangle([x_, y_, x_ + w_, y_ + h_],
                           outline=(255, 255, 255, 255), width=stroke_w)
        for child in el:
            _draw_element(child)

    _draw_element(root)
    return img


def _pil_to_surface(img: Image.Image) -> pygame.Surface:
    raw  = img.tobytes("raw", "RGBA")
    surf = pygame.image.fromstring(raw, img.size, "RGBA").convert_alpha()
    return surf


def _tint(surf: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
    """Return a new surface with white pixels coloured by `color`."""
    out = surf.copy()
    out.fill((*color, 0), special_flags=pygame.BLEND_RGBA_MAX)
    out.fill((*color, 255), special_flags=pygame.BLEND_RGB_MULT)
    return out


# ── public API ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def get(name: str, size: int = 18,
        color: tuple[int, int, int] = (210, 220, 240)) -> pygame.Surface:
    """Return a tinted, size×size pygame Surface for the named icon.

    `name` matches the SVG filename in app/assets/icons/ (without .svg).
    Falls back to a simple placeholder square if the file is missing.
    """
    svg_path = _ICON_DIR / f"{name}.svg"
    try:
        pil_img = _svg_to_pil(svg_path, size)
        surf    = _pil_to_surface(pil_img)
        return _tint(surf, color)
    except Exception:
        # Fallback: tiny hollow square
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(surf, (*color, 200), (1, 1, size - 2, size - 2), width=2)
        return surf
