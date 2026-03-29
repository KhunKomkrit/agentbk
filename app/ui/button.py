"""Pixel-style button widget."""

from __future__ import annotations
import pygame
from app.ui import font_manager

# palette
_NORMAL_BG  = ( 45,  55,  90)
_HOVER_BG   = ( 65,  85, 140)
_PRESS_BG   = ( 30,  40,  70)
_NORMAL_BD  = ( 80, 110, 180)
_HOVER_BD   = (120, 160, 220)
_TEXT_COL   = (210, 220, 240)
_RADIUS     = 8


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        icon: str = "",
        icon_surf: pygame.Surface | None = None,
        font_size: int = 15,
    ) -> None:
        self.rect = rect
        self.label = label
        self.icon = icon
        self.icon_surf = icon_surf
        self._font = font_manager.get(font_size)
        self._hovered = False
        self._pressed = False

    # ── event ──────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True when button is clicked (mouse-up inside)."""
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self._pressed
            self._pressed = False
            if was and self.rect.collidepoint(event.pos):
                return True
        return False

    # ── draw ───────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        if self._pressed:
            bg, bd = _PRESS_BG, _NORMAL_BD
        elif self._hovered:
            bg, bd = _HOVER_BG, _HOVER_BD
        else:
            bg, bd = _NORMAL_BG, _NORMAL_BD

        pygame.draw.rect(surface, bg, self.rect, border_radius=_RADIUS)
        pygame.draw.rect(surface, bd, self.rect, width=2, border_radius=_RADIUS)

        text_surf = self._font.render(self.label, True, _TEXT_COL)

        if self.icon_surf is not None:
            icon = self.icon_surf
            gap    = 6
            total_w = icon.get_width() + gap + text_surf.get_width()
            ix = self.rect.centerx - total_w // 2
            iy = self.rect.centery - icon.get_height() // 2
            surface.blit(icon, (ix, iy))
            surface.blit(text_surf, (ix + icon.get_width() + gap,
                                     self.rect.centery - text_surf.get_height() // 2))
        else:
            text = f"{self.icon} {self.label}".strip() if self.icon else self.label
            surf = self._font.render(text, True, _TEXT_COL)
            surface.blit(surf, (self.rect.centerx - surf.get_width() // 2,
                                self.rect.centery - surf.get_height() // 2))
