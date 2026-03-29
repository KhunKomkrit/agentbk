"""Chat scene — dynamic layout, Thai font, mini avatar header."""

from __future__ import annotations
import threading
import pygame
from app.ui.scene_manager import BaseScene
from app.ui import font_manager
from app.avatar.renderer import AvatarRenderer, AvatarState
from app.agent.router import AgentRouter
from app.agent.attachment import AttachmentResult, process_file, from_clipboard, clipboard_unsupported_msg

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
ATTACH_BG = ( 45,  50,  80)
ATTACH_HOV= ( 65,  75, 115)
PREVIEW_BG= ( 25,  28,  48)
RADIUS    = 10
HEADER_H  = 50
INPUT_H   = 46
PAD       = 10
PREVIEW_H = 64   # height of attachment preview strip above input

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
    __slots__ = ("is_user", "text", "thumb")
    def __init__(self, is_user: bool, text: str,
                 thumb: pygame.Surface | None = None) -> None:
        self.is_user = is_user
        self.text    = text
        self.thumb   = thumb   # optional 48×48 Surface for image attachments


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
        self._pending_attachment: AttachmentResult | None = None
        self._toast          = ""    # short message shown above input (e.g. clipboard notice)
        self._toast_ticks    = 0

        self._font      = font_manager.get(14)
        self._font_sm   = font_manager.get(12)
        self._font_bold = font_manager.get_bold(14)
        self._font_hint = font_manager.get(13)

        from app.ui import icon_manager
        self._icon_back     = icon_manager.get("arrow-left",    size=14, color=(200, 210, 230))
        self._icon_send     = icon_manager.get("send",          size=18, color=(230, 235, 255))
        self._icon_new_chat = icon_manager.get("pencil-square", size=13, color=(190, 205, 240))
        self._icon_attach   = icon_manager.get("paper-clip",    size=16, color=(200, 215, 240))
        self._icon_doc      = icon_manager.get("document",      size=20, color=(160, 180, 230))
        self._icon_dismiss  = icon_manager.get("x-mark",        size=12, color=(220, 160, 160))

        # Enable pygame file-drop events
        pygame.event.set_allowed(None)  # allow all event types

        self._last_size      = (-1, -1)
        self._back_rect      = pygame.Rect(0, 0, 1, 1)
        self._new_chat_rect  = pygame.Rect(0, 0, 1, 1)
        self._input_rect     = pygame.Rect(0, 0, 1, 1)
        self._send_rect      = pygame.Rect(0, 0, 1, 1)
        self._attach_rect    = pygame.Rect(0, 0, 1, 1)   # 📎 button
        self._preview_rect   = pygame.Rect(0, 0, 1, 1)   # attachment preview strip
        self._dismiss_rect   = pygame.Rect(0, 0, 1, 1)   # ✕ on preview
        self._back_hov       = False
        self._send_hov       = False
        self._new_chat_hov   = False
        self._attach_hov     = False
        self._bubble_max_w   = 200

        self._load_history()
        self._layout(win_w, win_h)

    # ── history helpers ───────────────────────────────────────────────────────

    def _load_history(self) -> None:
        """Sync _messages with ConversationMemory (skip tool messages).
        If memory is empty (e.g. cleared in Settings) resets to welcome message."""
        if not self._router:
            return
        msgs: list[_Msg] = []
        for m in self._router._memory.messages:
            if m.get("role") not in ("user", "assistant"):
                continue
            content = m.get("content", "")
            # Multimodal content (list of blocks) — extract text part for display.
            if isinstance(content, list):
                text = " ".join(b.get("text", "") for b in content
                                if isinstance(b, dict) and b.get("type") == "text")
            else:
                text = content
            if text.strip():
                msgs.append(_Msg(m["role"] == "user", text))
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
        # 📎 button is a square to the left of the input box
        attach_sz          = INPUT_H - 10
        self._attach_rect  = pygame.Rect(PAD, h - INPUT_H + 3, attach_sz, attach_sz)
        self._send_rect    = pygame.Rect(w - PAD - sw, h - INPUT_H + 3, sw, INPUT_H - 10)
        # Input box sits between 📎 and send
        inp_x              = PAD + attach_sz + 6
        self._input_rect   = pygame.Rect(inp_x, h - INPUT_H + 3,
                                         w - inp_x - PAD - sw - 6, INPUT_H - 10)
        # Attachment preview strip (only visible when _pending_attachment is set)
        self._preview_rect = pygame.Rect(PAD, h - INPUT_H - PREVIEW_H, w - PAD * 2, PREVIEW_H)
        self._dismiss_rect = pygame.Rect(
            self._preview_rect.right - 22, self._preview_rect.top + 4, 18, 18
        )
        self._bubble_max_w = max(80, w - PAD * 4)

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == _IDLE_TIMER:
            self.avatar.state = AvatarState.IDLE
            return

        # ── file drag-and-drop ────────────────────────────────────────────────
        if event.type == pygame.DROPFILE:
            self._load_attachment(event.file)
            return

        if event.type == pygame.MOUSEMOTION:
            self._back_hov     = self._back_rect.collidepoint(event.pos)
            self._send_hov     = self._send_rect.collidepoint(event.pos)
            self._new_chat_hov = self._new_chat_rect.collidepoint(event.pos)
            self._attach_hov   = self._attach_rect.collidepoint(event.pos)

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
            if self._attach_rect.collidepoint(event.pos):
                self._open_file_dialog()
                return
            # ✕ dismiss button on preview strip
            if (self._pending_attachment is not None
                    and self._dismiss_rect.collidepoint(event.pos)):
                self._pending_attachment = None
                return

        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - event.y * 20)

        if event.type == pygame.KEYDOWN:
            # Ctrl+V / Cmd+V — clipboard paste
            mods = pygame.key.get_mods()
            if event.key == pygame.K_v and (mods & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                result = from_clipboard()
                if result:
                    self._pending_attachment = result
                else:
                    self._set_toast(clipboard_unsupported_msg())
                return
            if event.key == pygame.K_RETURN:
                self._submit()
            elif event.key == pygame.K_BACKSPACE:
                self._input = self._input[:-1]
            elif event.unicode and event.unicode.isprintable():
                self._input += event.unicode

    def _submit(self) -> None:
        text = self._input.strip()
        att  = self._pending_attachment
        if not text and att is None:
            return
        if self._is_streaming:
            return
        self._input              = ""
        self._pending_attachment = None
        self._scroll             = 0
        self._is_streaming       = True
        self._streaming_msg      = None
        # Display text in bubble; show thumbnail alongside if image.
        display_text = text or f"[{att.filename}]" if att else text
        self._messages.append(_Msg(True, display_text,
                                   thumb=att.thumb if att else None))
        self.avatar.state = AvatarState.THINKING
        if self._router:
            self._router.start_stream(text, attachment=att)
        else:
            self._messages.append(_Msg(False, "(router ไม่ได้ต่อ)"))
            self._is_streaming = False
            self.avatar.state  = AvatarState.IDLE

    def _load_attachment(self, path: str) -> None:
        """Process a dropped/selected file in a background thread to avoid blocking the UI."""
        def _work():
            try:
                self._pending_attachment = process_file(path)
            except Exception as exc:
                self._set_toast(f"ไม่สามารถโหลดไฟล์: {exc}")
        threading.Thread(target=_work, daemon=True).start()

    def _open_file_dialog(self) -> None:
        """Show a native file-open dialog in a background thread."""
        def _work():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                path = filedialog.askopenfilename(
                    title="เลือกไฟล์",
                    filetypes=[
                        ("รูปภาพ", "*.png *.jpg *.jpeg *.webp"),
                        ("PDF",    "*.pdf"),
                        ("ข้อความ / Code", "*.txt *.md *.py *.js *.ts *.json *.yaml *.yml"),
                        ("ทุกไฟล์", "*.*"),
                    ],
                )
                root.destroy()
                if path:
                    self._pending_attachment = process_file(path)
            except Exception as exc:
                self._set_toast(f"ไม่สามารถเปิด file dialog: {exc}")
        threading.Thread(target=_work, daemon=True).start()

    def _set_toast(self, msg: str, ticks: int = 180) -> None:
        """Show a temporary notice message above the input area."""
        self._toast       = msg
        self._toast_ticks = ticks

    # ── update — poll router queue each frame ─────────────────────────────────

    def _bake_thumb(self, att: "AttachmentResult") -> None:
        """Convert thumb_raw bytes → pygame.Surface on the main thread (SDL2-safe)."""
        if att.thumb is None and att.thumb_raw is not None:
            from app.agent.attachment import THUMB_SIZE
            try:
                surf = pygame.image.frombuffer(att.thumb_raw, THUMB_SIZE, "RGB")
                att.thumb = surf.convert()
            except Exception:
                att.thumb = surf  # fallback if convert() unavailable yet
            att.thumb_raw = None  # free raw bytes

    def update(self) -> None:
        self.avatar.update()
        self._ctick += 1
        if self._ctick >= 30:
            self._cursor = not self._cursor
            self._ctick  = 0
        # Convert pending attachment thumbnail on main thread (SDL2 surface ops not thread-safe)
        if self._pending_attachment is not None:
            self._bake_thumb(self._pending_attachment)
        # Countdown toast
        if self._toast_ticks > 0:
            self._toast_ticks -= 1
            if self._toast_ticks == 0:
                self._toast = ""

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
        if self._pending_attachment:
            self._draw_preview_strip(surface, w, h)
        if self._toast:
            self._draw_toast(surface, w, h)
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
        # Reserve extra room at the bottom when a preview strip is showing.
        bottom_reserve = (PREVIEW_H if self._pending_attachment else 0) + INPUT_H + 4
        area = pygame.Rect(0, HEADER_H, w, h - HEADER_H - bottom_reserve)
        clip = surface.get_clip()
        surface.set_clip(area)

        bubbles: list[tuple[pygame.Surface, bool]] = []
        total_h = 0
        gap     = 8

        for msg in reversed(self._messages):
            lines = _wrap(msg.text, self._font, self._bubble_max_w - 24)
            lh    = self._font.get_linesize()
            bh    = lh * len(lines) + 16
            # If the message has a thumbnail, extend the bubble height.
            if msg.thumb:
                bh += msg.thumb.get_height() + 8
            bw = min(self._bubble_max_w,
                     max(self._font.size(ln)[0] for ln in lines) + 24)
            if msg.thumb:
                bw = max(bw, msg.thumb.get_width() + 24)
            bsurf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(bsurf, USER_BUB if msg.is_user else BOT_BUB,
                             (0, 0, bw, bh), border_radius=RADIUS)
            y_off = 8
            if msg.thumb:
                bsurf.blit(msg.thumb, (12, y_off))
                y_off += msg.thumb.get_height() + 8
            for i, ln in enumerate(lines):
                t = self._font.render(ln, True, TEXT_COL)
                bsurf.blit(t, (12, y_off + i * lh))
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
        # ── 📎 attach button ─────────────────────────────────────────────────
        att_col = ATTACH_HOV if self._attach_hov else ATTACH_BG
        # Highlight when an attachment is pending.
        if self._pending_attachment:
            att_col = (70, 110, 60)
        pygame.draw.rect(surface, att_col, self._attach_rect, border_radius=8)
        ai = self._icon_attach
        surface.blit(ai, (self._attach_rect.centerx - ai.get_width() // 2,
                          self._attach_rect.centery - ai.get_height() // 2))

        # ── text input ───────────────────────────────────────────────────────
        pygame.draw.rect(surface, INPUT_BG,  self._input_rect, border_radius=8)
        pygame.draw.rect(surface, INPUT_BD,  self._input_rect, width=2, border_radius=8)

        disp = self._input + ("|" if self._cursor else " ")
        t = (self._font.render(disp, True, TEXT_COL) if disp.strip()
             else self._font_hint.render("พิมพ์ข้อความ... (ลากไฟล์ หรือ �)", True, HINT_COL))

        max_tw = self._input_rect.width - 16
        if t.get_width() > max_tw:
            c = pygame.Surface((max_tw, t.get_height()), pygame.SRCALPHA)
            c.blit(t, (max_tw - t.get_width(), 0))
            t = c
        surface.blit(t, (self._input_rect.x + 8,
                         self._input_rect.centery - t.get_height() // 2))

        # ── send button ──────────────────────────────────────────────────────
        sc = SEND_HOV if self._send_hov else SEND_BG
        pygame.draw.rect(surface, sc, self._send_rect, border_radius=8)
        ic = self._icon_send
        surface.blit(ic, (self._send_rect.centerx - ic.get_width() // 2,
                          self._send_rect.centery - ic.get_height() // 2))

    def _draw_preview_strip(self, surface: pygame.Surface, w: int, h: int) -> None:
        """Draw the attachment preview strip above the input row."""
        att = self._pending_attachment
        if att is None:
            return
        pr = self._preview_rect
        pygame.draw.rect(surface, PREVIEW_BG, pr, border_radius=8)
        pygame.draw.rect(surface, (60, 70, 100), pr, width=1, border_radius=8)

        x = pr.x + 8
        cy = pr.centery

        # Thumbnail (image) or kind icon (pdf/text)
        if att.thumb and att.kind == "image":
            th = att.thumb
            th_y = cy - th.get_height() // 2
            surface.blit(th, (x, th_y))
            x += th.get_width() + 8
        else:
            di = self._icon_doc
            surface.blit(di, (x, cy - di.get_height() // 2))
            x += di.get_width() + 8

        # Filename + kind label
        name_surf = self._font_sm.render(att.filename, True, TEXT_COL)
        kind_surf = self._font_sm.render(
            {"image": "รูปภาพ", "pdf": "PDF", "text": "ไฟล์ข้อความ"}.get(att.kind, att.kind),
            True, HINT_COL)
        name_y = cy - (name_surf.get_height() + 2 + kind_surf.get_height()) // 2
        surface.blit(name_surf, (x, name_y))
        surface.blit(kind_surf, (x, name_y + name_surf.get_height() + 2))

        # ✕ dismiss button
        pygame.draw.rect(surface, (70, 40, 40), self._dismiss_rect, border_radius=5)
        xi = self._icon_dismiss
        surface.blit(xi, (self._dismiss_rect.centerx - xi.get_width() // 2,
                          self._dismiss_rect.centery - xi.get_height() // 2))

    def _draw_toast(self, surface: pygame.Surface, w: int, h: int) -> None:
        """Draw a short notice above the input area."""
        lbl = self._font_sm.render(self._toast, True, (240, 200, 120))
        tx  = PAD
        ty  = (h - INPUT_H - (PREVIEW_H if self._pending_attachment else 0)
               - lbl.get_height() - 6)
        bg_rect = pygame.Rect(tx - 4, ty - 3, lbl.get_width() + 8, lbl.get_height() + 6)
        pygame.draw.rect(surface, (40, 35, 20), bg_rect, border_radius=6)
        surface.blit(lbl, (tx, ty))
