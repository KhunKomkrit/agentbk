"""Main scene — avatar + [Chat] [Voice] [Settings] buttons. Dynamic layout."""

from __future__ import annotations
import pygame
from app.ui.scene_manager import BaseScene
from app.ui.button import Button
from app.ui import font_manager
from app.avatar.renderer import AvatarRenderer, AvatarState

BG        = ( 18,  18,  30)
AVATAR_BG = ( 22,  22,  38)
TITLE_COL = (160, 180, 220)
CLOSE_COL = (180,  70,  70)
CLOSE_HOV = (220, 100, 100)

_STATE_INFO = {
    AvatarState.IDLE:     ("idle",      ( 70, 180,  70)),
    AvatarState.THINKING: ("thinking…", (180, 180,  60)),
    AvatarState.TALKING:  ("talking",   ( 70, 130, 210)),
    AvatarState.ERROR:    ("error",     (200,  70,  70)),
    AvatarState.LOADING:  ("loading…",  (120, 140, 255)),
}

HEADER_H   = 32
BTN_H      = 38
BTN_GAP    = 10
BTN_BOTTOM = 20   # gap from bottom edge to buttons
CARD_PAD   = 12
MIN_SHOW_BUTTONS = 260  # hide buttons below this height


class MainScene(BaseScene):
    def __init__(self, win_w: int, win_h: int, router=None) -> None:
        self._router = router
        self.avatar = AvatarRenderer()
        self._font_title = font_manager.get_bold(14)
        self._font_state = font_manager.get(11)
        self._init_complete = False
        self._loading_messages: list[str] = []
        self._loading_dots = 0
        self._loading_tick = 0
        self._ollama_status = ""      # latest ollama_progress text
        self._ollama_frac: float = 0.0  # 0.0–1.0 download fraction

        # load SVG icons (16×16 tinted to match text colour)
        from app.ui import icon_manager
        _ic = (210, 220, 240)
        _chat_icon     = icon_manager.get("chat",       size=16, color=_ic)
        _settings_icon = icon_manager.get("settings",   size=16, color=_ic)

        # buttons (rects updated in _layout)
        self._btn_chat     = Button(pygame.Rect(0, 0, 1, 1), "Chat",     icon_surf=_chat_icon,     font_size=13)
        self._btn_settings = Button(pygame.Rect(0, 0, 1, 1), "Settings", icon_surf=_settings_icon, font_size=13)

        self._close_rect = pygame.Rect(0, 0, 20, 20)
        self._close_hov  = False
        self._last_size  = (-1, -1)

    # ── layout ───────────────────────────────────────────────────────────────

    def _layout(self, w: int, h: int) -> None:
        self._last_size = (w, h)
        self._close_rect = pygame.Rect(w - 26, 6, 20, 20)

        if h >= MIN_SHOW_BUTTONS:
            by    = h - BTN_BOTTOM - BTN_H
            n     = 2
            bw    = max(80, (w - CARD_PAD * 2 - BTN_GAP * (n - 1)) // n)
            total = bw * n + BTN_GAP * (n - 1)
            bx    = (w - total) // 2
            self._btn_chat.rect     = pygame.Rect(bx,              by, bw, BTN_H)
            self._btn_settings.rect = pygame.Rect(bx + bw + BTN_GAP, by, bw, BTN_H)

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        w, h = self._last_size

        if event.type == pygame.MOUSEMOTION:
            self._close_hov = self._close_rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._close_rect.collidepoint(event.pos):
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return

        # Disable button interaction during loading
        if not self._init_complete:
            return

        if h >= MIN_SHOW_BUTTONS:
            if self._btn_chat.handle_event(event):
                self._go_chat()
            if self._btn_settings.handle_event(event):
                self._go_settings()

    def update(self) -> None:
        self.avatar.update()
        self._loading_tick += 1
        
        # Poll for initialization progress messages
        if not self._init_complete and self._router:
            while True:
                try:
                    chunk = self._router.result_queue.get_nowait()
                    if chunk.kind == "init_progress":
                        self._loading_messages.append(chunk.text)
                        if self._router.is_ready:
                            self._init_complete = True
                            self.avatar.state = AvatarState.IDLE
                    elif chunk.kind == "ollama_progress":
                        self._ollama_status = chunk.text
                        # parse fraction from e.g. "pulling 45%" → 0.45
                        import re
                        m = re.search(r"(\d+)%", chunk.text)
                        if m:
                            self._ollama_frac = int(m.group(1)) / 100.0
                        else:
                            self._ollama_frac = 0.0
                except Exception:
                    break
        
        # Set loading state if not ready
        if not self._init_complete:
            self.avatar.state = AvatarState.LOADING
            self._loading_dots = (self._loading_tick // 20) % 4

    # ── draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        if (w, h) != self._last_size:
            self._layout(w, h)

        surface.fill(BG)

        show_buttons = h >= MIN_SHOW_BUTTONS

        # avatar card — fills most of the window
        card_bottom = (h - BTN_H - BTN_BOTTOM - BTN_GAP) if show_buttons else (h - 8)
        card_rect   = pygame.Rect(CARD_PAD, HEADER_H, w - CARD_PAD * 2,
                                  card_bottom - HEADER_H)
        if card_rect.height > 10:
            pygame.draw.rect(surface, AVATAR_BG, card_rect, border_radius=14)

        # avatar — scaled to fit card
        av_scale = min(
            (card_rect.width  - 16) / self.avatar.width,
            (card_rect.height - 32) / self.avatar.height,
            1.0,          # never upscale beyond native
        )
        from app.avatar.renderer import PIXEL
        scaled_pixel = max(1, int(PIXEL * av_scale))

        # draw avatar at scaled pixel size
        self._draw_avatar_scaled(surface, card_rect, scaled_pixel)

        # state badge (hide if too small)
        if card_rect.height > 40:
            label, color = _STATE_INFO[self.avatar.state]
            st  = self._font_state.render(label, True, color)
            dot_r = 4
            gap   = 5
            total_w = dot_r * 2 + gap + st.get_width()
            bx  = w // 2 - total_w // 2
            by  = card_rect.bottom - 20
            pygame.draw.circle(surface, color, (bx + dot_r, by + st.get_height() // 2), dot_r)
            surface.blit(st, (bx + dot_r * 2 + gap, by))

        # title (hide if window very narrow)
        if w >= 200:
            tt = self._font_title.render("AgentBK", True, TITLE_COL)
            surface.blit(tt, (w // 2 - tt.get_width() // 2, 8))

        # close button
        col = CLOSE_HOV if self._close_hov else CLOSE_COL
        pygame.draw.circle(surface, col, self._close_rect.center, 9)
        pygame.draw.circle(surface, (40, 40, 60), self._close_rect.center, 9, 2)

        # main buttons
        if show_buttons:
            # Dim buttons if not ready
            if not self._init_complete:
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 100))
                surface.blit(overlay, (0, 0))
            
            self._btn_chat.draw(surface)
            self._btn_settings.draw(surface)
        
        # Loading overlay
        if not self._init_complete:
            self._draw_loading_overlay(surface, w, h)

    def _draw_loading_overlay(self, surface: pygame.Surface, w: int, h: int) -> None:
        """Draw loading overlay with progress messages and optional download bar."""
        # Semi-transparent background
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 220))
        surface.blit(overlay, (0, 0))
        
        # Loading box
        box_w = min(w - 40, 320)
        box_h = min(h - 80, 220)
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        
        # Box background with border
        pygame.draw.rect(surface, (25, 28, 45), box_rect, border_radius=12)
        pygame.draw.rect(surface, (80, 90, 140), box_rect, 2, border_radius=12)
        
        # Title
        font_title = font_manager.get_bold(16)
        title = font_title.render("Initializing AgentBK", True, (180, 200, 255))
        surface.blit(title, (box_x + (box_w - title.get_width()) // 2, box_y + 18))
        
        # Animated dots
        dots = "●" * self._loading_dots + "◦" * (3 - self._loading_dots)
        font_small = font_manager.get(11)
        dots_surf = font_small.render(dots, True, (100, 120, 180))
        surface.blit(dots_surf, (box_x + (box_w - dots_surf.get_width()) // 2, box_y + 42))
        
        # Progress messages (completed steps with checkmarks)
        font_msg = font_manager.get(13)
        y = box_y + 65
        lh = 22
        for msg in self._loading_messages[-4:]:
            check_x = box_x + 28
            pygame.draw.circle(surface, (60, 175, 75), (check_x, y + 7), 6)
            pygame.draw.line(surface, (20, 25, 40), (check_x - 2, y + 7), (check_x, y + 10), 2)
            pygame.draw.line(surface, (20, 25, 40), (check_x, y + 10), (check_x + 3, y + 4), 2)
            txt = font_msg.render(msg, True, (160, 180, 220))
            surface.blit(txt, (check_x + 14, y))
            y += lh
        
        # Ollama download status + progress bar
        if self._ollama_status and not any("Ollama" in m for m in self._loading_messages):
            bar_x = box_x + 20
            bar_y = box_y + box_h - 58
            bar_w = box_w - 40

            # Status text
            status_col = (220, 100, 60) if "⚠" in self._ollama_status else (140, 170, 220)
            st_surf = font_small.render(self._ollama_status[:45], True, status_col)
            surface.blit(st_surf, (bar_x, bar_y))

            # Progress bar (only when we have a real fraction)
            if self._ollama_frac > 0:
                bar_y += 18
                pygame.draw.rect(surface, (40, 44, 70), pygame.Rect(bar_x, bar_y, bar_w, 8), border_radius=4)
                fill_w = int(bar_w * self._ollama_frac)
                if fill_w > 0:
                    pygame.draw.rect(surface, (70, 140, 220), pygame.Rect(bar_x, bar_y, fill_w, 8), border_radius=4)
                pct_surf = font_small.render(f"{int(self._ollama_frac * 100)}%", True, (120, 150, 210))
                surface.blit(pct_surf, (bar_x + bar_w - pct_surf.get_width(), bar_y + 12))
        
        # Hint text at bottom
        elif self._loading_tick > 600:
            hint_font = font_manager.get(11)
            hint_surf = hint_font.render("This may take a moment...", True, (100, 115, 165))
            surface.blit(hint_surf, (box_x + (box_w - hint_surf.get_width()) // 2, box_y + box_h - 28))
    
    def _draw_avatar_scaled(self, surface: pygame.Surface,
                             card: pygame.Rect, pixel: int) -> None:
        target_size = 16 * pixel
        full = pygame.Surface((self.avatar.width, self.avatar.height), pygame.SRCALPHA)
        full.fill((0, 0, 0, 0))
        self.avatar.draw(full, 0, 0)
        scaled = pygame.transform.smoothscale(full, (target_size, target_size))
        ax = card.centerx - target_size // 2
        ay = card.y + (card.height - target_size) // 2 - 8
        surface.blit(scaled, (ax, ay))


    # ── navigation ───────────────────────────────────────────────────────────

    def _go_chat(self) -> None:
        from app.ui.chat_scene import ChatScene
        w, h = self._last_size
        self.manager.push(ChatScene(w, h, self.avatar, self._router))

    def _go_settings(self) -> None:
        from app.ui.settings_scene import SettingsScene
        w, h = self._last_size
        self.manager.push(SettingsScene(w, h, router=self._router))
