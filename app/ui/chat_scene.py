"""Chat scene — dynamic layout, Thai font, mini avatar header."""

from __future__ import annotations
import pygame
from app.ui.scene_manager import BaseScene
from app.ui import font_manager
from app.avatar.renderer import AvatarRenderer, AvatarState
from app.agent.router import AgentRouter

BG        = ( 18,  18,  30)
HEADER_BG = ( 22,  22,  38)
USER_BUB  = ( 55,  90, 165)
BOT_BUB   = ( 35,  40,  65)
TEXT_COL  = (215, 220, 240)
HINT_COL  = ( 90,  95, 130)
INPUT_BG  = ( 30,  32,  52)
INPUT_BD  = ( 70, 110, 190)
SEND_BG   = ( 60, 110, 200)
SEND_HOV  = ( 80, 140, 230)
BACK_COL  = ( 80,  90, 130)
BACK_HOV  = (120, 135, 180)
RADIUS    = 10
HEADER_H  = 50
INPUT_H   = 46
PAD       = 10

_IDLE_TIMER = pygame.USEREVENT + 10


def _wrap(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    """Word-wrap with character-level fallback for Thai / CJK text."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for word in words:
            candidate = f"{cur} {word}".strip() if cur else word
            if font.size(candidate)[0] <= max_w:
                cur = candidate
            else:
                if cur:
                    lines.append(cur)
                # Word itself too wide → break character by character
                if font.size(word)[0] > max_w:
                    rem = word
                    while rem:
                        for i in range(len(rem), 0, -1):
                            if font.size(rem[:i])[0] <= max_w:
                                lines.append(rem[:i])
                                rem = rem[i:]
                                break
                        else:
                            lines.append(rem[0])
                            rem = rem[1:]
                    cur = ""
                else:
                    cur = word
        if cur:
            lines.append(cur)
    return lines or [""]


class _Msg:
    __slots__ = ("is_user", "text")
    def __init__(self, is_user: bool, text: str) -> None:
        self.is_user = is_user
        self.text    = text


_WELCOME = "สวัสดี! ฉันคือ AgentBK พิมพ์อะไรก็ได้เลยนะ :)"

NEW_CHAT_COL = ( 55,  65, 110)
NEW_CHAT_HOV = ( 80,  95, 155)


class ChatScene(BaseScene):
    def __init__(self, win_w: int, win_h: int, avatar: AvatarRenderer,
                 router: AgentRouter | None = None) -> None:
        self.avatar  = avatar
        self._router = router
        self._messages: list[_Msg] = [_Msg(False, _WELCOME)]
        self._input          = ""
        self._cursor         = True
        self._ctick          = 0
        self._scroll         = 0
        self._is_streaming   = False
        self._streaming_msg: _Msg | None = None
        self._tool_indicator = ""

        self._font      = font_manager.get(14)
        self._font_sm   = font_manager.get(12)
        self._font_bold = font_manager.get_bold(14)
        self._font_hint = font_manager.get(13)

        from app.ui import icon_manager
        self._icon_back     = icon_manager.get("arrow-left",    size=14, color=(200, 210, 230))
        self._icon_send     = icon_manager.get("send",          size=18, color=(230, 235, 255))
        self._icon_new_chat = icon_manager.get("pencil-square", size=13, color=(190, 205, 240))

        self._last_size      = (-1, -1)
        self._back_rect      = pygame.Rect(0, 0, 1, 1)
        self._new_chat_rect  = pygame.Rect(0, 0, 1, 1)
        self._input_rect     = pygame.Rect(0, 0, 1, 1)
        self._send_rect      = pygame.Rect(0, 0, 1, 1)
        self._back_hov       = False
        self._send_hov       = False
        self._new_chat_hov   = False
        self._bubble_max_w   = 200

        self._load_history()
        self._layout(win_w, win_h)

    # ── history helpers ───────────────────────────────────────────────────────

    def _load_history(self) -> None:
        """Sync _messages with ConversationMemory (skip tool messages).
        If memory is empty (e.g. cleared in Settings) resets to welcome message."""
        if not self._router:
            return
        msgs = [
            _Msg(m["role"] == "user", m.get("content", ""))
            for m in self._router._memory.messages
            if m.get("role") in ("user", "assistant") and m.get("content", "").strip()
        ]
        self._messages = msgs if msgs else [_Msg(False, _WELCOME)]

    def _new_chat(self) -> None:
        """Clear history and reset UI to welcome state."""
        if self._is_streaming:
            return
        if self._router:
            self._router.clear_history()
        self._messages = [_Msg(False, _WELCOME)]
        self._scroll   = 0

    def on_enter(self) -> None:
        self.avatar.state = AvatarState.IDLE
        if not self._is_streaming:
            self._load_history()   # sync UI after Settings clear-history or other changes
            self._scroll = 0

    # ── layout ───────────────────────────────────────────────────────────────

    def _layout(self, w: int, h: int) -> None:
        self._last_size    = (w, h)
        sw                 = 40
        btn_h              = 26
        btn_y              = (HEADER_H - btn_h) // 2
        avatar_w           = 48
        # New-chat button sits left of mini avatar
        nc_w               = 30
        nc_x               = w - 6 - avatar_w - 6 - nc_w
        self._new_chat_rect = pygame.Rect(nc_x, btn_y, nc_w, btn_h)
        self._back_rect    = pygame.Rect(6, btn_y, 58, btn_h)
        self._send_rect    = pygame.Rect(w - PAD - sw, h - INPUT_H + 3, sw, INPUT_H - 10)
        self._input_rect   = pygame.Rect(PAD, h - INPUT_H + 3,
                                         w - PAD * 2 - sw - 6, INPUT_H - 10)
        self._bubble_max_w = max(80, w - PAD * 4)

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == _IDLE_TIMER:
            self.avatar.state = AvatarState.IDLE
            return

        if event.type == pygame.MOUSEMOTION:
            self._back_hov     = self._back_rect.collidepoint(event.pos)
            self._send_hov     = self._send_rect.collidepoint(event.pos)
            self._new_chat_hov = self._new_chat_rect.collidepoint(event.pos)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._back_rect.collidepoint(event.pos):
                self.manager.pop()
                return
            if self._new_chat_rect.collidepoint(event.pos):
                self._new_chat()
                return
            if self._send_rect.collidepoint(event.pos):
                self._submit()
                return

        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - event.y * 20)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._submit()
            elif event.key == pygame.K_BACKSPACE:
                self._input = self._input[:-1]
            elif event.unicode and event.unicode.isprintable():
                self._input += event.unicode

    def _submit(self) -> None:
        text = self._input.strip()
        if not text or self._is_streaming:
            return
        self._input         = ""
        self._scroll        = 0
        self._is_streaming  = True
        self._streaming_msg = None
        self._messages.append(_Msg(True, text))
        self.avatar.state   = AvatarState.THINKING
        if self._router:
            self._router.start_stream(text)
        else:
            self._messages.append(_Msg(False, "(router ไม่ได้ต่อ)"))
            self._is_streaming = False
            self.avatar.state  = AvatarState.IDLE

    # ── update — poll router queue each frame ─────────────────────────────────

    def update(self) -> None:
        self.avatar.update()
        self._ctick += 1
        if self._ctick >= 30:
            self._cursor = not self._cursor
            self._ctick  = 0

        if not self._router or not self._is_streaming:
            return

        for item in self._router.drain(max_items=30):
            if item.kind == "chunk":
                if self._streaming_msg is None:
                    self._streaming_msg = _Msg(False, "")
                    self._messages.append(self._streaming_msg)
                self._streaming_msg.text += item.text
                self._scroll = 0   # auto-scroll to bottom while streaming

            elif item.kind == "tool_use":
                self._tool_indicator = f"tool: {item.text}"
                self.avatar.state    = AvatarState.THINKING

            elif item.kind == "done":
                self._is_streaming   = False
                self._tool_indicator = ""
                self._scroll         = 0
                self.avatar.state    = AvatarState.TALKING
                pygame.time.set_timer(_IDLE_TIMER, 1500, loops=1)
                # auto-speak reply via TTS
                if self._router and self._streaming_msg:
                    self._router.speaker.speak(self._streaming_msg.text)
                self._streaming_msg  = None

            elif item.kind == "error":
                self._messages.append(_Msg(False, f"! {item.text}"))
                self._is_streaming   = False
                self._streaming_msg  = None
                self._tool_indicator = ""
                self._scroll         = 0
                self.avatar.state    = AvatarState.ERROR

    # ── draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        if (w, h) != self._last_size:
            self._layout(w, h)

        surface.fill(BG)
        self._draw_header(surface, w)
        self._draw_messages(surface, w, h)
        self._draw_input(surface, w, h)

    def _draw_header(self, surface: pygame.Surface, w: int) -> None:
        pygame.draw.rect(surface, HEADER_BG, pygame.Rect(0, 0, w, HEADER_H))

        col = BACK_HOV if self._back_hov else BACK_COL
        pygame.draw.rect(surface, col, self._back_rect, border_radius=7)
        bt   = self._font_sm.render("กลับ", True, (200, 210, 230))
        ic   = self._icon_back
        gap  = 4
        tw   = ic.get_width() + gap + bt.get_width()
        bx   = self._back_rect.centerx - tw // 2
        by_i = self._back_rect.centery - ic.get_height() // 2
        by_t = self._back_rect.centery - bt.get_height() // 2
        surface.blit(ic, (bx, by_i))
        surface.blit(bt, (bx + ic.get_width() + gap, by_t))

        tt = self._font_bold.render("AgentBK Chat", True, (160, 180, 220))
        surface.blit(tt, (w // 2 - tt.get_width() // 2,
                          HEADER_H // 2 - tt.get_height() // 2))

        # New Chat button
        nc_col = NEW_CHAT_HOV if self._new_chat_hov else NEW_CHAT_COL
        pygame.draw.rect(surface, nc_col, self._new_chat_rect, border_radius=7)
        ic_nc = self._icon_new_chat
        surface.blit(ic_nc, (self._new_chat_rect.centerx - ic_nc.get_width() // 2,
                              self._new_chat_rect.centery - ic_nc.get_height() // 2))

        mini = self._mini_avatar()
        surface.blit(mini, (w - mini.get_width() - 6,
                             (HEADER_H - mini.get_height()) // 2))

    def _mini_avatar(self) -> pygame.Surface:
        full = pygame.Surface((self.avatar.width, self.avatar.height), pygame.SRCALPHA)
        full.fill((0, 0, 0, 0))
        self.avatar.draw(full, 0, 0)
        return pygame.transform.smoothscale(full, (48, 48))

    def _draw_messages(self, surface: pygame.Surface, w: int, h: int) -> None:
        area = pygame.Rect(0, HEADER_H, w, h - HEADER_H - INPUT_H - 4)
        clip = surface.get_clip()
        surface.set_clip(area)

        bubbles: list[tuple[pygame.Surface, bool]] = []
        total_h = 0
        gap     = 8

        for msg in reversed(self._messages):
            lines = _wrap(msg.text, self._font, self._bubble_max_w - 24)
            lh    = self._font.get_linesize()
            bh    = lh * len(lines) + 16
            bw    = min(self._bubble_max_w,
                        max(self._font.size(ln)[0] for ln in lines) + 24)
            bsurf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(bsurf, USER_BUB if msg.is_user else BOT_BUB,
                             (0, 0, bw, bh), border_radius=RADIUS)
            for i, ln in enumerate(lines):
                t = self._font.render(ln, True, TEXT_COL)
                bsurf.blit(t, (12, 8 + i * lh))
            bubbles.append((bsurf, msg.is_user))
            total_h += bh + gap

        max_scroll = max(0, total_h - area.height)
        scroll     = min(self._scroll, max_scroll)
        y = area.bottom - gap + scroll
        for bsurf, is_user in bubbles:
            bw, bh = bsurf.get_size()
            y -= bh
            x = (w - bw - PAD) if is_user else PAD
            surface.blit(bsurf, (x, y))
            y -= gap

        # tool indicator pill (shown while a tool is executing)
        if self._tool_indicator:
            lbl     = self._font_sm.render(self._tool_indicator, True, (130, 170, 255))
            pill_w  = lbl.get_width() + 20
            pill_h  = lbl.get_height() + 8
            pill_x  = PAD
            pill_y  = area.bottom - pill_h - 6
            pygame.draw.rect(surface, (35, 45, 80),
                             pygame.Rect(pill_x, pill_y, pill_w, pill_h), border_radius=10)
            surface.blit(lbl, (pill_x + 10, pill_y + 4))

        surface.set_clip(clip)

    def _draw_input(self, surface: pygame.Surface, w: int, h: int) -> None:
        pygame.draw.rect(surface, INPUT_BG,  self._input_rect, border_radius=8)
        pygame.draw.rect(surface, INPUT_BD,  self._input_rect, width=2, border_radius=8)

        disp = self._input + ("|" if self._cursor else " ")
        t = (self._font.render(disp, True, TEXT_COL) if disp.strip()
             else self._font_hint.render("พิมพ์ข้อความ...", True, HINT_COL))

        max_tw = self._input_rect.width - 16
        if t.get_width() > max_tw:
            c = pygame.Surface((max_tw, t.get_height()), pygame.SRCALPHA)
            c.blit(t, (max_tw - t.get_width(), 0))
            t = c
        surface.blit(t, (self._input_rect.x + 8,
                         self._input_rect.centery - t.get_height() // 2))

        sc = SEND_HOV if self._send_hov else SEND_BG
        pygame.draw.rect(surface, sc, self._send_rect, border_radius=8)
        ic = self._icon_send
        surface.blit(ic, (self._send_rect.centerx - ic.get_width() // 2,
                          self._send_rect.centery - ic.get_height() // 2))
