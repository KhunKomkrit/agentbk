"""AvatarCanvas — PIL-based pixel avatar widget for CustomTkinter.

Renders the same 16×16 grid logic as app.avatar.renderer, but outputs to a
PIL Image → ImageTk.PhotoImage displayed in a CTkLabel.  Animation runs via
Tkinter's after() at ~30fps instead of pygame's main loop.
"""
from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING

from PIL import Image
import customtkinter as ctk

from app.avatar.renderer import AvatarState

if TYPE_CHECKING:
    pass

PIXEL = 8    # pixels per grid cell  →  canvas = 128×128
GRID  = 16   # grid dimensions

# ── Palette ───────────────────────────────────────────────────────────────
_HEAD   = ( 42,  45,  78, 255)
_HEAD_L = ( 60,  64, 108, 255)
_SCREEN = ( 22,  24,  45, 255)
_EYE_W  = (185, 205, 250, 255)
_EYE_P  = ( 55,  95, 215, 255)
_EYE_G  = (230, 235, 255, 255)
_LID    = ( 38,  40,  70, 255)
_SMILE  = (120, 175, 255, 255)
_MOUTH_D= ( 12,  14,  30, 255)
_TEETH  = (200, 220, 255, 255)
_X_COL  = (210,  70,  70, 255)
_ZZZ    = (130, 140, 195, 255)
_CHEEK  = ( 55,  50, 100, 255)
_LED_I  = ( 80, 220, 120, 255)
_LED_TH = (255, 200,  50, 255)
_LED_TK = ( 80, 200, 255, 255)
_LED_E  = (220,  60,  60, 255)
_BG     = ( 22,  24,  45, 255)    # background / face-screen base


class AvatarCanvas(ctk.CTkLabel):
    """A CTkLabel that self-animates the pixel avatar."""

    def __init__(self, parent, size: int = 128, **kwargs) -> None:
        self._av_size = size
        self._pixel = size // GRID   # e.g. 128//16 = 8

        # Start with a blank image; actual render happens in _animate
        blank = Image.new("RGBA", (size, size), _BG)
        self._ctk_img = ctk.CTkImage(light_image=blank, dark_image=blank, size=(size, size))
        super().__init__(parent, image=self._ctk_img, text="", **kwargs)

        # Animation state
        self.state: AvatarState = AvatarState.LOADING
        self._tick       = 0
        self._blink_t    = 0
        self._blink_open = True
        self._talk_frame = 0
        self._droop      = 0.0
        self._bob        = 0.0
        self._shake      = 0
        self._led_pulse  = 0.0

        self._after_id: str | None = None
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._animate()

    def stop(self) -> None:
        self._running = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    # ── Animation loop ────────────────────────────────────────────────────

    def _animate(self) -> None:
        if not self._running:
            return
        self._update()
        img = self._render()
        self._ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(self._av_size, self._av_size))
        self.configure(image=self._ctk_img)
        self._after_id = self.after(33, self._animate)   # ~30 fps

    # ── State update (mirrors renderer.py logic) ──────────────────────────

    def _update(self) -> None:
        self._tick += 1

        # Idle bob
        self._bob = math.sin(self._tick * 0.05) * 2

        # Blink (idle only)
        if self.state == AvatarState.IDLE:
            self._blink_t += 1
            if self._blink_t > 120:
                self._blink_open = False
            if self._blink_t > 126:
                self._blink_open = True
                self._blink_t = 0
        else:
            self._blink_open = True
            self._blink_t = 0

        # Talking mouth
        if self.state == AvatarState.TALKING:
            self._talk_frame = (self._tick // 5) % 2

        # Droopy lids
        if self.state == AvatarState.THINKING:
            self._droop = min(1.0, self._droop + 0.0015)
        else:
            self._droop = max(0.0, self._droop - 0.06)

        # Error shake
        if self.state == AvatarState.ERROR:
            self._shake = int(math.sin(self._tick * 0.9) * 2)
        else:
            self._shake = 0

        # LED pulse
        self._led_pulse = math.sin(self._tick * 0.12) * 0.5 + 0.5

    # ── PIL rendering ─────────────────────────────────────────────────────

    def _render(self) -> Image.Image:
        p = self._pixel
        size = self._av_size
        bob_y = int(self._bob) if self.state == AvatarState.IDLE else 0
        ox = self._shake   # screen-pixel offset (1-2 px)
        oy = bob_y          # screen-pixel offset (1-2 px)

        img = Image.new("RGBA", (size, size), _BG)

        def px(col: int, row: int, color: tuple, w: int = 1, h: int = 1) -> None:
            x0 = ox + col * p
            y0 = oy + row * p
            x1 = x0 + p * w
            y1 = y0 + p * h
            # Clip to image bounds
            x0 = max(0, min(size - 1, x0))
            y0 = max(0, min(size - 1, y0))
            x1 = max(1, min(size, x1))
            y1 = max(1, min(size, y1))
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    img.putpixel((xx, yy), color)

        # Head
        for r in range(2, 12):
            for c in range(2, 14):
                px(c, r, _HEAD)
        for c in range(3, 13):
            px(c, 1, _HEAD)
        for c in range(3, 13):
            px(c, 12, _HEAD)
        for c in range(4, 12):
            px(c, 1, _HEAD_L)
        for r in range(3, 12):
            for c in range(3, 13):
                px(c, r, _SCREEN)
        px(3,  8, _CHEEK)
        px(12, 8, _CHEEK)

        # LED
        if self.state == AvatarState.IDLE:
            led_col = _LED_I
        elif self.state == AvatarState.THINKING:
            v = int(self._led_pulse * 60)
            led_col = (255, 200 + v // 3, max(0, 50 - v // 2), 255)
        elif self.state == AvatarState.TALKING:
            led_col = _LED_TK
        elif self.state == AvatarState.LOADING:
            v = int(self._led_pulse * 100)
            led_col = (80 + v // 2, 140 + v // 2, 255, 255)
        else:  # ERROR — fast blink
            led_col = _LED_E if (self._tick // 6) % 2 == 0 else _HEAD
        px(7, 0, led_col)
        px(8, 0, led_col)

        # Eyes
        droop_rows = int(self._droop * 3)
        blink = not self._blink_open

        if self.state == AvatarState.ERROR:
            for eye_cx in (5, 10):
                for r in (4, 5, 6):
                    px(eye_cx - 1, r, _SCREEN, w=3)
                px(eye_cx - 1, 4, _X_COL)
                px(eye_cx + 1, 4, _X_COL)
                px(eye_cx,     5, _X_COL)
                px(eye_cx - 1, 6, _X_COL)
                px(eye_cx + 1, 6, _X_COL)
        else:
            for eye_cx in (5, 10):
                if blink or droop_rows >= 3:
                    px(eye_cx - 1, 5, _LID, w=3)
                else:
                    for r in (4, 5, 6):
                        px(eye_cx - 1, r, _EYE_W, w=3)
                    px(eye_cx,     5, _EYE_P)
                    px(eye_cx + 1, 4, _EYE_G)
                    for lid in range(droop_rows):
                        px(eye_cx - 1, 4 + lid, _LID, w=3)

        # Mouth
        if self.state == AvatarState.TALKING:
            if self._talk_frame == 1:
                px(5, 8, _MOUTH_D, w=6, h=2)
                px(5, 8, _TEETH,   w=6)
            else:
                px(5,  8, _SMILE)
                px(10, 8, _SMILE)
                px(6,  9, _SMILE, w=4)
        elif self.state == AvatarState.THINKING:
            px(5, 9, _SMILE, w=6)
        elif self.state == AvatarState.ERROR:
            px(5,  8, _SMILE, w=6)
            px(4,  9, _SMILE)
            px(11, 9, _SMILE)
        else:
            px(5,  8, _SMILE)
            px(10, 8, _SMILE)
            px(6,  9, _SMILE, w=4)

        # Thinking dots
        if self.state == AvatarState.THINKING and self._droop < 0.85:
            dot_count = (self._tick // 25) % 4
            for i in range(3):
                color = _ZZZ if i < dot_count else _SCREEN
                px(14, 3 - i, color)

        # Scale up with nearest-neighbor (pixel-perfect)
        return img.resize((self._av_size, self._av_size), Image.NEAREST)
