"""Pixel bot-face avatar — expressive eyes + mouth per state."""
from __future__ import annotations

import math
import pygame
from dataclasses import dataclass, field
from enum import Enum, auto

PIXEL = 8   # one "pixel unit" = 8 screen pixels  →  canvas = 128×128 px


class AvatarState(Enum):
    IDLE     = auto()
    THINKING = auto()
    TALKING  = auto()
    ERROR    = auto()
    LOADING  = auto()   # system initializing


# ── Palette ───────────────────────────────────────────────────────────────
_HEAD   = ( 42,  45,  78)   # bot head / body
_HEAD_L = ( 60,  64, 108)   # lighter edge highlight
_SCREEN = ( 22,  24,  45)   # face-screen interior
_EYE_W  = (185, 205, 250)   # eye iris / white
_EYE_P  = ( 55,  95, 215)   # pupil
_EYE_G  = (230, 235, 255)   # pupil glint
_LID    = ( 38,  40,  70)   # eyelid (droopy)
_SMILE  = (120, 175, 255)   # smile / mouth line
_MOUTH_D= ( 12,  14,  30)   # open-mouth cavity
_TEETH  = (200, 220, 255)   # teeth row
_X_COL  = (210,  70,  70)   # X-eye for error
_ZZZ    = (130, 140, 195)   # zzz dot / sleep hint
_CHEEK  = ( 55,  50, 100)   # cheek tint
_LED_I  = ( 80, 220, 120)   # idle   LED — green
_LED_TH = (255, 200,  50)   # think  LED — yellow
_LED_TK = ( 80, 200, 255)   # talk   LED — cyan
_LED_E  = (220,  60,  60)   # error  LED — red


# ── Drawing helpers ───────────────────────────────────────────────────────

def _px(surface: pygame.Surface, ox: int, oy: int,
        col: int, row: int, color: tuple,
        w: int = 1, h: int = 1) -> None:
    """Draw w×h pixel-units at grid (col, row) offset by (ox, oy)."""
    pygame.draw.rect(
        surface, color,
        (ox + col * PIXEL, oy + row * PIXEL, PIXEL * w, PIXEL * h),
    )


# ── Avatar ────────────────────────────────────────────────────────────────

@dataclass
class AvatarRenderer:
    state: AvatarState = AvatarState.IDLE

    _tick:       int   = field(default=0,    init=False)
    _blink_t:    int   = field(default=0,    init=False)
    _blink_open: bool  = field(default=True, init=False)
    _talk_frame: int   = field(default=0,    init=False)
    _droop:      float = field(default=0.0,  init=False)   # 0–1 sleepiness
    _bob:        float = field(default=0.0,  init=False)
    _shake:      int   = field(default=0,    init=False)
    _led_pulse:  float = field(default=0.0,  init=False)

    width:  int = field(default=16 * PIXEL, init=False)
    height: int = field(default=16 * PIXEL, init=False)

    # ── update ────────────────────────────────────────────────────────────

    def update(self) -> None:
        self._tick += 1

        # idle bob
        self._bob = math.sin(self._tick * 0.05) * 2

        # blink (idle only): every ~120 ticks, lasts 6 ticks
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

        # talking mouth
        if self.state == AvatarState.TALKING:
            self._talk_frame = (self._tick // 5) % 2

        # droopy lids (thinking: slowly get sleepy; other states: snap back)
        if self.state == AvatarState.THINKING:
            self._droop = min(1.0, self._droop + 0.0015)
        else:
            self._droop = max(0.0, self._droop - 0.06)

        # error shake
        if self.state == AvatarState.ERROR:
            self._shake = int(math.sin(self._tick * 0.9) * 2)
        else:
            self._shake = 0

        # LED pulse
        self._led_pulse = math.sin(self._tick * 0.12) * 0.5 + 0.5

    # ── draw ──────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, x: int, y: int) -> None:
        bob_y = int(self._bob) if self.state == AvatarState.IDLE else 0
        ox = x + self._shake
        oy = y + bob_y

        self._draw_head(surface, ox, oy)
        self._draw_led(surface, ox, oy)
        self._draw_eyes(surface, ox, oy)
        self._draw_mouth(surface, ox, oy)
        self._draw_extras(surface, ox, oy)

    # ── head ──────────────────────────────────────────────────────────────

    def _draw_head(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        # Main head block: cols 2-13, rows 2-11
        for r in range(2, 12):
            for c in range(2, 14):
                _px(surface, ox, oy, c, r, _HEAD)
        # Top edge (trimmed corners): row 1, cols 3-12
        for c in range(3, 13):
            _px(surface, ox, oy, c, 1, _HEAD)
        # Bottom edge: row 12, cols 3-12
        for c in range(3, 13):
            _px(surface, ox, oy, c, 12, _HEAD)
        # Highlight top edge
        for c in range(4, 12):
            _px(surface, ox, oy, c, 1, _HEAD_L)
        # Face screen interior: cols 3-12, rows 3-11
        for r in range(3, 12):
            for c in range(3, 13):
                _px(surface, ox, oy, c, r, _SCREEN)
        # Cheek blush hints
        _px(surface, ox, oy,  3, 8, _CHEEK)
        _px(surface, ox, oy, 12, 8, _CHEEK)

    # ── LED ───────────────────────────────────────────────────────────────

    def _draw_led(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        # Tiny antenna stalk + LED at top-center (col 7-8, row 0-1)
        _px(surface, ox, oy, 7, 1, _HEAD)   # stalk base (already drawn, just LED)
        if self.state == AvatarState.IDLE:
            color = _LED_I
        elif self.state == AvatarState.THINKING:
            # Slow pulse between yellow and dim
            v = int(self._led_pulse * 60)
            color = (255, 200 + v // 3, max(0, 50 - v // 2))
        elif self.state == AvatarState.TALKING:
            color = _LED_TK
        elif self.state == AvatarState.LOADING:
            # Pulsing cyan/blue for loading
            v = int(self._led_pulse * 100)
            color = (80 + v // 2, 140 + v // 2, 255)
        else:   # ERROR — fast blink
            color = _LED_E if (self._tick // 6) % 2 == 0 else _HEAD
        _px(surface, ox, oy, 7, 0, color)
        _px(surface, ox, oy, 8, 0, color)   # 2-pixel LED

    # ── eyes ──────────────────────────────────────────────────────────────

    def _draw_eyes(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        if self.state == AvatarState.ERROR:
            self._draw_eye_x(surface, ox, oy, 5)
            self._draw_eye_x(surface, ox, oy, 10)
            return

        # Droop: 0→awake, 1→fully closed
        droop_rows = int(self._droop * 3)        # 0, 1, 2, 3
        blink = not self._blink_open
        self._draw_eye_open(surface, ox, oy, 5,  droop_rows, blink)
        self._draw_eye_open(surface, ox, oy, 10, droop_rows, blink)

    def _draw_eye_open(self, surface: pygame.Surface, ox: int, oy: int,
                       cx: int, droop: int, blink: bool) -> None:
        """Draw one eye centered at column cx, rows 4-6.
        droop = 0 (open) … 3 (closed line).  blink = instant close."""
        # Eye area: (cx-1)–(cx+1) × rows 4–6
        if blink or droop >= 3:
            # Fully closed = single horizontal slit
            _px(surface, ox, oy, cx - 1, 5, _LID, w=3, h=1)
            return

        # Draw iris
        for r in (4, 5, 6):
            _px(surface, ox, oy, cx - 1, r, _EYE_W, w=3, h=1)
        # Pupil
        _px(surface, ox, oy, cx, 5, _EYE_P)
        # Glint (top-right)
        _px(surface, ox, oy, cx + 1, 4, _EYE_G)

        # Droopy lid covers top rows of eye
        for lid in range(droop):
            _px(surface, ox, oy, cx - 1, 4 + lid, _LID, w=3, h=1)

    def _draw_eye_x(self, surface: pygame.Surface, ox: int, oy: int,
                    cx: int) -> None:
        """X-shaped eye for error state."""
        # Clear eye area to screen color
        for r in (4, 5, 6):
            _px(surface, ox, oy, cx - 1, r, _SCREEN, w=3, h=1)
        # Draw X diagonals
        _px(surface, ox, oy, cx - 1, 4, _X_COL)
        _px(surface, ox, oy, cx + 1, 4, _X_COL)
        _px(surface, ox, oy, cx,     5, _X_COL)
        _px(surface, ox, oy, cx - 1, 6, _X_COL)
        _px(surface, ox, oy, cx + 1, 6, _X_COL)

    # ── mouth ─────────────────────────────────────────────────────────────

    def _draw_mouth(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        if self.state == AvatarState.TALKING:
            if self._talk_frame == 1:   # open
                _px(surface, ox, oy, 5, 8, _MOUTH_D, w=6, h=2)
                _px(surface, ox, oy, 5, 8, _TEETH,   w=6, h=1)  # teeth row
            else:
                self._draw_smile(surface, ox, oy)

        elif self.state == AvatarState.THINKING:
            # Flat / sleepy mouth — thin horizontal line
            _px(surface, ox, oy, 5, 9, _SMILE, w=6, h=1)

        elif self.state == AvatarState.ERROR:
            # Frown: flat top + corners pointing down
            _px(surface, ox, oy, 5, 8, _SMILE, w=6, h=1)
            _px(surface, ox, oy, 4, 9, _SMILE)
            _px(surface, ox, oy, 11, 9, _SMILE)

        else:   # IDLE
            self._draw_smile(surface, ox, oy)

    def _draw_smile(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        # Smile: two corner pixels + bottom arc
        _px(surface, ox, oy, 5,  8, _SMILE)          # left corner
        _px(surface, ox, oy, 10, 8, _SMILE)           # right corner
        _px(surface, ox, oy, 6,  9, _SMILE, w=4)      # bottom arc

    # ── extras ────────────────────────────────────────────────────────────

    def _draw_extras(self, surface: pygame.Surface, ox: int, oy: int) -> None:
        # Thinking dots (…) above-right of head, fade in with droop
        if self.state == AvatarState.THINKING and self._droop < 0.85:
            dot_count = (self._tick // 25) % 4
            for i in range(3):
                color = _ZZZ if i < dot_count else _SCREEN
                _px(surface, ox, oy, 14, 3 - i, color)


# ── kept for any legacy imports ───────────────────────────────────────────
BODY_MAP: list[str] = []
COLOR_MAP: dict[str, tuple | None] = {}
