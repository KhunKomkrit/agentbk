"""Chat panel — message history + text input box."""

from __future__ import annotations

import pygame
from dataclasses import dataclass, field
from enum import Enum, auto


class Role(Enum):
    USER = auto()
    BOT  = auto()


@dataclass
class Message:
    role: Role
    text: str


# colours
BG          = ( 18,  18,  30)
PANEL_BG    = ( 28,  28,  45)
USER_BUBBLE = ( 60,  90, 160)
BOT_BUBBLE  = ( 40,  45,  70)
TEXT_COL    = (220, 220, 240)
HINT_COL    = (100, 100, 130)
INPUT_BG    = ( 35,  35,  55)
INPUT_BORD  = ( 80,  80, 120)
INPUT_FOCUS = ( 80, 130, 200)
SCROLLBAR   = ( 60,  60,  90)
RADIUS      = 10


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


class ChatPanel:
    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self.messages: list[Message] = []
        self._input_text: str = ""
        self._cursor_visible: bool = True
        self._cursor_tick: int = 0
        self._scroll_offset: int = 0  # pixels scrolled from bottom

        pygame.font.init()
        self._font      = pygame.font.SysFont("monospace", 14)
        self._font_bold = pygame.font.SysFont("monospace", 14, bold=True)
        self._font_hint = pygame.font.SysFont("monospace", 13)

        self._input_h = 44
        self._padding = 12
        self._bubble_max_w = rect.width - self._padding * 4

    # ── public API ──────────────────────────────────────────────────────────

    def add_message(self, role: Role, text: str) -> None:
        self.messages.append(Message(role, text))
        self._scroll_offset = 0  # jump to bottom on new message

    def get_input(self) -> str:
        return self._input_text

    def clear_input(self) -> None:
        self._input_text = ""

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Returns submitted text when user presses Enter, else None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                text = self._input_text.strip()
                if text:
                    self.clear_input()
                    return text
            elif event.key == pygame.K_BACKSPACE:
                self._input_text = self._input_text[:-1]
            else:
                if event.unicode and event.unicode.isprintable():
                    self._input_text += event.unicode
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_offset = max(0, self._scroll_offset - event.y * 20)
        return None

    def update(self) -> None:
        self._cursor_tick += 1
        if self._cursor_tick >= 30:
            self._cursor_visible = not self._cursor_visible
            self._cursor_tick = 0

    def draw(self, surface: pygame.Surface) -> None:
        # panel background
        pygame.draw.rect(surface, PANEL_BG, self.rect, border_radius=12)

        chat_rect = pygame.Rect(
            self.rect.x,
            self.rect.y,
            self.rect.width,
            self.rect.height - self._input_h - self._padding,
        )
        input_rect = pygame.Rect(
            self.rect.x + self._padding,
            self.rect.bottom - self._input_h,
            self.rect.width - self._padding * 2,
            self._input_h - self._padding // 2,
        )

        self._draw_messages(surface, chat_rect)
        self._draw_input(surface, input_rect)

    # ── private ─────────────────────────────────────────────────────────────

    def _draw_messages(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        # build all bubble surfaces bottom-up
        bubbles: list[tuple[pygame.Surface, bool]] = []  # (surf, is_user)
        total_h = 0
        gap = 8

        for msg in reversed(self.messages):
            is_user = msg.role == Role.USER
            lines = _wrap_text(msg.text, self._font, self._bubble_max_w - 24)
            line_h = self._font.get_linesize()
            bh = line_h * len(lines) + 16
            bw = min(self._bubble_max_w, max(self._font.size(ln)[0] for ln in lines) + 24)

            bsurf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            color = USER_BUBBLE if is_user else BOT_BUBBLE
            pygame.draw.rect(bsurf, color, (0, 0, bw, bh), border_radius=RADIUS)
            for i, ln in enumerate(lines):
                t = self._font.render(ln, True, TEXT_COL)
                bsurf.blit(t, (12, 8 + i * line_h))

            bubbles.append((bsurf, is_user))
            total_h += bh + gap

        # clip to area
        clip = surface.get_clip()
        surface.set_clip(area)

        max_scroll = max(0, total_h - area.height)
        scroll = min(self._scroll_offset, max_scroll)

        y = area.bottom - gap + scroll
        for bsurf, is_user in bubbles:
            bw, bh = bsurf.get_size()
            y -= bh
            if is_user:
                x = area.right - bw - self._padding
            else:
                x = area.left + self._padding
            surface.blit(bsurf, (x, y))
            y -= gap

        surface.set_clip(clip)

    def _draw_input(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, INPUT_BG, rect, border_radius=8)
        pygame.draw.rect(surface, INPUT_FOCUS, rect, width=2, border_radius=8)

        display = self._input_text
        if self._cursor_visible:
            display += "|"

        if display:
            t = self._font.render(display, True, TEXT_COL)
        else:
            t = self._font_hint.render("พิมพ์ข้อความ แล้วกด Enter ...", True, HINT_COL)

        # clip text inside input box
        max_text_w = rect.width - 16
        if t.get_width() > max_text_w:
            # show tail of text
            clip_surf = pygame.Surface((max_text_w, t.get_height()), pygame.SRCALPHA)
            clip_surf.blit(t, (max_text_w - t.get_width(), 0))
            t = clip_surf

        ty = rect.y + (rect.height - t.get_height()) // 2
        surface.blit(t, (rect.x + 8, ty))
