"""Settings scene — dynamic layout."""

from __future__ import annotations
import os
import pygame
from app.ui.scene_manager import BaseScene
from app.ui import font_manager

BG        = ( 18,  18,  30)
HEADER_BG = ( 22,  22,  38)
CARD_BG   = ( 26,  28,  48)
TEXT_COL  = (215, 220, 240)
MUTED     = (100, 110, 150)
SEL_COL   = ( 70, 120, 210)
UNSEL_COL = ( 50,  55,  85)
SAVE_BG   = ( 50, 160,  90)
SAVE_HOV  = ( 70, 190, 110)
BACK_COL  = ( 80,  90, 130)
BACK_HOV  = (120, 135, 180)
TOGGLE_ON = ( 50, 160,  90)
TOGGLE_OFF= ( 60,  60,  90)
INPUT_BG  = ( 32,  34,  58)
INPUT_FOC = ( 40,  60, 120)
HEADER_H  = 50
PAD       = 14
RADIUS    = 8

_PROVIDERS = ["anthropic", "openai", "ollama"]
_PROVIDER_LABELS = {
    "anthropic": "Anthropic Claude",
    "openai":    "OpenAI GPT",
    "ollama":    "Ollama (Local)",
}
_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "ollama":    ["llama3", "mistral", "gemma3"],
}

_MCP_PRESETS = [
    ("Space MCP",      "http://localhost:8000/mcp"),
    ("JIRA",           "http://localhost:9000/mcp"),
    ("Google Cal",     "http://localhost:9001/mcp"),
]

DEL_COL  = (160,  50,  50)
DEL_HOV  = (210,  70,  70)
EDIT_COL = ( 60,  80, 130)
EDIT_HOV = ( 80, 110, 170)
ADD_COL  = ( 45, 110,  70)
ADD_HOV  = ( 60, 145,  90)


class SettingsScene(BaseScene):
    def __init__(self, win_w: int, win_h: int, router=None) -> None:
        self._router = router
        self._provider      = os.getenv("ACTIVE_PROVIDER", "anthropic")
        self._model_idx     = 0
        self._always_on_top = True
        self._saved_flash   = 0
        self._clear_flash   = 0
        self._clear_hov     = False
        self._clear_rect    = pygame.Rect(0, 0, 1, 1)

        # Multi-MCP state
        from app.agent.mcp_config import load_servers
        self._mcp_servers: list[dict] = load_servers()
        self._mcp_edit_idx: int | None = None   # None=closed, -1=new, 0..n=edit
        self._mcp_edit_name = ""
        self._mcp_edit_url  = ""
        self._mcp_input_focus: str | None = None  # "name" | "url"
        self._cursor_tick   = 0
        # Rects set during _draw_mcp (content-surface coords)
        self._mcp_add_rect        = pygame.Rect(0, 0, 1, 1)
        self._mcp_row_toggle:  list[pygame.Rect] = []
        self._mcp_row_edit:    list[pygame.Rect] = []
        self._mcp_row_del:     list[pygame.Rect] = []
        self._mcp_form_name_r = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_url_r  = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_preset_rects: list[pygame.Rect] = []
        self._mcp_form_save_r = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_cancel_r = pygame.Rect(0, 0, 1, 1)
        self._mcp_edit_headers: str = ""
        self._mcp_form_headers_r = pygame.Rect(0, 0, 1, 1)

        self._font      = font_manager.get(13)
        self._font_bold = font_manager.get_bold(14)
        self._font_sm   = font_manager.get(12)
        self._font_h    = font_manager.get_bold(12)

        from app.ui import icon_manager
        self._icon_back    = icon_manager.get("arrow-left",      size=14, color=(200, 210, 230))
        self._icon_settings= icon_manager.get("settings",        size=16, color=(160, 180, 220))
        self._icon_check   = icon_manager.get("check",           size=14, color=(100, 220, 130))
        self._icon_prev    = icon_manager.get("chevron-left",    size=16, color=(210, 220, 240))
        self._icon_next    = icon_manager.get("chevron-right",   size=16, color=(210, 220, 240))
        self._icon_edit    = icon_manager.get("pencil-square",   size=13, color=(210, 225, 255))
        self._icon_del     = icon_manager.get("x-mark",          size=13, color=(255, 200, 200))

        # Knowledge Base state
        self._kb_docs:     list[dict] = []
        self._kb_path_buf: str        = ""
        self._kb_path_focused: bool   = False
        self._kb_path_rect   = pygame.Rect(0, 0, 1, 1)
        self._kb_add_rect    = pygame.Rect(0, 0, 1, 1)
        self._kb_del_rects:  list[pygame.Rect] = []
        self._kb_status: str = ""  # flash message
        self._kb_status_tick = 0
        self._kb_ingest_error: str = ""
        self._refresh_kb_docs()

        self._last_size      = (-1, -1)
        self._back_rect      = pygame.Rect(0, 0, 1, 1)
        self._save_rect      = pygame.Rect(0, 0, 1, 1)
        self._prov_rects:  list[pygame.Rect] = []
        self._model_prev   = pygame.Rect(0, 0, 1, 1)
        self._model_next   = pygame.Rect(0, 0, 1, 1)
        self._toggle_rect  = pygame.Rect(0, 0, 1, 1)
        self._back_hov     = False
        self._save_hov     = False
        self._scroll_y     = 0
        self._content_h    = 0

        self._layout(win_w, win_h)

    def _refresh_kb_docs(self) -> None:
        try:
            from app.rag.store import RAGStore
            self._kb_docs = RAGStore().list_documents()
        except Exception:
            self._kb_docs = []

    # ── layout ───────────────────────────────────────────────────────────────

    def _layout(self, w: int, h: int) -> None:
        self._last_size  = (w, h)
        self._back_rect  = pygame.Rect(6, (HEADER_H - 26) // 2, 58, 26)
        sw, sh           = 90, 34
        self._save_rect  = pygame.Rect(w - PAD - sw, h - sh - PAD, sw, sh)

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and self._kb_path_focused:
            if event.key == pygame.K_ESCAPE:
                self._kb_path_focused = False
            elif event.key == pygame.K_RETURN:
                self._kb_path_focused = False
                self._ingest_kb_file()
            elif event.key == pygame.K_BACKSPACE:
                self._kb_path_buf = self._kb_path_buf[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable():
                    self._kb_path_buf += ch
            return

        if event.type == pygame.KEYDOWN and self._mcp_input_focus:
            if event.key == pygame.K_ESCAPE:
                self._mcp_input_focus = None
            elif event.key == pygame.K_RETURN:
                self._mcp_input_focus = None
            elif event.key == pygame.K_BACKSPACE:
                if self._mcp_input_focus == "name":
                    self._mcp_edit_name = self._mcp_edit_name[:-1]
                elif self._mcp_input_focus == "url":
                    self._mcp_edit_url = self._mcp_edit_url[:-1]
                else:
                    self._mcp_edit_headers = self._mcp_edit_headers[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable():
                    if self._mcp_input_focus == "name":
                        self._mcp_edit_name += ch
                    elif self._mcp_input_focus == "url":
                        self._mcp_edit_url += ch
                    else:
                        self._mcp_edit_headers += ch
            return

        if event.type == pygame.MOUSEMOTION:
            self._back_hov  = self._back_rect.collidepoint(event.pos)
            self._save_hov  = self._save_rect.collidepoint(event.pos)
            scroll_pos_m    = (event.pos[0], event.pos[1] - HEADER_H + self._scroll_y)
            self._clear_hov = self._clear_rect.collidepoint(scroll_pos_m)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 4:
            self._scroll_y = max(0, self._scroll_y - 20)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 5:
            _, wh = self._last_size
            max_scroll = max(0, self._content_h - (wh - HEADER_H - 50))
            self._scroll_y = min(max_scroll, self._scroll_y + 20)
            return

        if event.type != pygame.MOUSEBUTTONUP or event.button != 1:
            return

        # Unfocus URL input if clicking elsewhere
        raw_pos = event.pos
        scroll_pos = (raw_pos[0], raw_pos[1] - HEADER_H + self._scroll_y)

        if self._back_rect.collidepoint(raw_pos):
            self.manager.pop()
            return
        if self._save_rect.collidepoint(raw_pos):
            self._save()
            return
        for i, r in enumerate(self._prov_rects):
            if r.collidepoint(scroll_pos):
                self._provider  = _PROVIDERS[i]
                self._model_idx = 0
                return
        if self._model_prev.collidepoint(scroll_pos):
            models = _MODELS[self._provider]
            self._model_idx = (self._model_idx - 1) % len(models)
        if self._model_next.collidepoint(scroll_pos):
            models = _MODELS[self._provider]
            self._model_idx = (self._model_idx + 1) % len(models)
        if self._toggle_rect.collidepoint(scroll_pos):
            self._always_on_top = not self._always_on_top

        # ── Multi-MCP interactions ────────────────────────────────────────────
        if self._mcp_add_rect.collidepoint(scroll_pos):
            self._mcp_edit_idx     = -1
            self._mcp_edit_name    = ""
            self._mcp_edit_url     = ""
            self._mcp_edit_headers = ""
            self._mcp_input_focus  = "name"
        for i, r in enumerate(self._mcp_row_toggle):
            if r.collidepoint(scroll_pos):
                self._mcp_servers[i]["enabled"] = not self._mcp_servers[i].get("enabled", False)
        for i, r in enumerate(self._mcp_row_edit):
            if r.collidepoint(scroll_pos):
                self._mcp_edit_idx   = i
                self._mcp_edit_name  = self._mcp_servers[i].get("name", "")
                self._mcp_edit_url   = self._mcp_servers[i].get("url", "")
                raw_h = self._mcp_servers[i].get("headers") or {}
                import json as _json
                self._mcp_edit_headers = _json.dumps(raw_h, ensure_ascii=False) if raw_h else ""
                self._mcp_input_focus  = "name"
        for i, r in enumerate(self._mcp_row_del):
            if r.collidepoint(scroll_pos):
                if self._mcp_edit_idx == i:
                    self._mcp_edit_idx = None
                elif isinstance(self._mcp_edit_idx, int) and self._mcp_edit_idx > i:
                    self._mcp_edit_idx -= 1
                self._mcp_servers.pop(i)
        if self._mcp_form_name_r.collidepoint(scroll_pos):
            self._mcp_input_focus = "name"
        elif self._mcp_form_url_r.collidepoint(scroll_pos):
            self._mcp_input_focus = "url"
        elif self._mcp_form_headers_r.collidepoint(scroll_pos):
            self._mcp_input_focus = "headers"
        else:
            # Clicking outside inputs defocuses (but only if not clicking a form button)
            if not (self._mcp_form_save_r.collidepoint(scroll_pos) or
                    self._mcp_form_cancel_r.collidepoint(scroll_pos) or
                    any(r.collidepoint(scroll_pos) for r in self._mcp_form_preset_rects)):
                self._mcp_input_focus = None
        for i, r in enumerate(self._mcp_form_preset_rects):
            if r.collidepoint(scroll_pos):
                _, url = _MCP_PRESETS[i]
                self._mcp_edit_url = url
        if self._mcp_form_save_r.collidepoint(scroll_pos) and self._mcp_edit_idx is not None:
            if self._mcp_edit_name or self._mcp_edit_url:
                import json as _json
                headers: dict = {}
                try:
                    if self._mcp_edit_headers.strip():
                        parsed = _json.loads(self._mcp_edit_headers)
                        if isinstance(parsed, dict):
                            headers = parsed
                except Exception:
                    pass
                entry = {
                    "name":    self._mcp_edit_name,
                    "url":     self._mcp_edit_url,
                    "headers": headers,
                    "enabled": True,
                }
                if self._mcp_edit_idx == -1:
                    self._mcp_servers.append(entry)
                else:
                    entry["enabled"] = self._mcp_servers[self._mcp_edit_idx].get("enabled", True)
                    self._mcp_servers[self._mcp_edit_idx] = entry
            self._mcp_edit_idx    = None
            self._mcp_input_focus = None
        if self._mcp_form_cancel_r.collidepoint(scroll_pos):
            self._mcp_edit_idx    = None
            self._mcp_input_focus = None

        # KB interactions
        if self._kb_path_rect.collidepoint(scroll_pos):
            self._kb_path_focused = True
        elif self._kb_add_rect.collidepoint(scroll_pos):
            self._ingest_kb_file()
        else:
            self._kb_path_focused = False
        for i, r in enumerate(self._kb_del_rects):
            if r.collidepoint(scroll_pos) and i < len(self._kb_docs):
                try:
                    from app.rag.store import RAGStore
                    RAGStore().delete_document(self._kb_docs[i]["doc_id"])
                    self._refresh_kb_docs()
                    self._kb_status = "ลบแล้ว"
                    self._kb_status_tick = 90
                except Exception as exc:
                    self._kb_status = str(exc)[:40]
                    self._kb_status_tick = 120

        if self._clear_rect.collidepoint(scroll_pos):
            if self._router:
                self._router.clear_history()
            self._clear_flash = 90

    def _save(self) -> None:
        env_path = ".env"
        lines: list[str] = []
        written: set[str] = set()
        updates = {
            "ACTIVE_PROVIDER": self._provider,
        }
        if os.path.exists(env_path):
            for line in open(env_path):
                key = line.split("=")[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}\n")
                    written.add(key)
                else:
                    lines.append(line)
        for k, v in updates.items():
            if k not in written:
                lines.append(f"{k}={v}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
        # Save MCP servers to JSON config
        from app.agent.mcp_config import save_servers
        save_servers(self._mcp_servers)
        self._saved_flash = 90
        # Reload dotenv + reconnect MCP after save
        from dotenv import load_dotenv
        load_dotenv(override=True)
        if self._router:
            self._router.reload_mcp()

    def _ingest_kb_file(self) -> None:
        path_str = self._kb_path_buf.strip()
        if not path_str:
            return
        import threading, os
        from pathlib import Path as _Path

        def _do():
            try:
                from app.rag.store import RAGStore
                from app.rag.ingestor import ingest_file
                p = _Path(os.path.expanduser(path_str))
                if not p.exists():
                    self._kb_status = f"ไม่พบไฟล์: {p.name}"
                else:
                    store = RAGStore()
                    ingest_file(p, store)
                    self._kb_status = f"เพิ่ม {p.name} แล้ว"
                    self._refresh_kb_docs()
            except Exception as exc:
                self._kb_status = str(exc)[:50]
            self._kb_status_tick = 120
            self._kb_path_buf = ""

        threading.Thread(target=_do, daemon=True).start()
        self._kb_status = "กำลังประมวลผล…"
        self._kb_status_tick = 9999

    # ── update ───────────────────────────────────────────────────────────────

    def update(self) -> None:
        if self._saved_flash > 0:
            self._saved_flash -= 1
        if self._clear_flash > 0:
            self._clear_flash -= 1
        if self._kb_status_tick > 0:
            self._kb_status_tick -= 1
        self._cursor_tick = (self._cursor_tick + 1) % 60

    # ── draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        if (w, h) != self._last_size:
            self._layout(w, h)

        surface.fill(BG)

        # Draw scrollable content onto an offscreen surface
        content_w = w
        content_surf = pygame.Surface((content_w, max(h, 800)), pygame.SRCALPHA)
        content_surf.fill(BG)

        y = PAD
        y = self._draw_provider(content_surf, w, y)
        y = self._draw_model(content_surf, w, y + PAD)
        y = self._draw_display(content_surf, w, y + PAD)
        y = self._draw_mcp(content_surf, w, y + PAD)
        y = self._draw_kb(content_surf, w, y + PAD)
        y = self._draw_danger(content_surf, w, y + PAD)
        self._content_h = y + PAD

        # Blit scrolled content below header
        clip_rect = pygame.Rect(0, HEADER_H, w, h - HEADER_H - 50)
        surface.set_clip(clip_rect)
        surface.blit(content_surf, (0, HEADER_H - self._scroll_y))
        surface.set_clip(None)

        self._draw_header(surface, w)
        self._draw_save(surface)

        # Scroll indicator
        content_visible = h - HEADER_H - 50
        if self._content_h > content_visible:
            bar_h = max(20, int(content_visible * content_visible / self._content_h))
            bar_y = HEADER_H + int(self._scroll_y * (content_visible - bar_h) /
                                   max(1, self._content_h - content_visible))
            pygame.draw.rect(surface, (60, 65, 100),
                             pygame.Rect(w - 4, bar_y, 3, bar_h), border_radius=2)

    def _draw_header(self, surface: pygame.Surface, w: int) -> None:
        pygame.draw.rect(surface, HEADER_BG, pygame.Rect(0, 0, w, HEADER_H))
        col = BACK_HOV if self._back_hov else BACK_COL
        pygame.draw.rect(surface, col, self._back_rect, border_radius=7)
        bt   = self._font_sm.render("กลับ", True, (200, 210, 230))
        ic   = self._icon_back
        gap  = 4
        tw   = ic.get_width() + gap + bt.get_width()
        bx   = self._back_rect.centerx - tw // 2
        surface.blit(ic, (bx, self._back_rect.centery - ic.get_height() // 2))
        surface.blit(bt, (bx + ic.get_width() + gap,
                          self._back_rect.centery - bt.get_height() // 2))

        # title with settings icon
        si  = self._icon_settings
        tt  = self._font_bold.render("Settings", True, (160, 180, 220))
        ttw = si.get_width() + 6 + tt.get_width()
        tx  = w // 2 - ttw // 2
        ty  = HEADER_H // 2
        surface.blit(si, (tx, ty - si.get_height() // 2))
        surface.blit(tt, (tx + si.get_width() + 6, ty - tt.get_height() // 2))

    def _draw_provider(self, surface: pygame.Surface, w: int, y: int) -> int:
        cx = PAD
        cw = w - PAD * 2
        ch = 16 + len(_PROVIDERS) * 34 + 8
        pygame.draw.rect(surface, CARD_BG, pygame.Rect(cx, y, cw, ch), border_radius=RADIUS)
        ht = self._font_h.render("LLM Provider", True, MUTED)
        surface.blit(ht, (cx + 10, y + 8))
        self._prov_rects = []
        ry = y + 26
        for i, name in enumerate(_PROVIDERS):
            r = pygame.Rect(cx + 10, ry, cw - 20, 26)
            self._prov_rects.append(r)
            selected = (self._provider == name)
            pygame.draw.rect(surface, SEL_COL if selected else UNSEL_COL, r, border_radius=6)
            # radio dot
            dot_x = r.x + 14
            dot_y = r.centery
            pygame.draw.circle(surface, TEXT_COL, (dot_x, dot_y), 5, 0 if selected else 2)
            t = self._font.render(_PROVIDER_LABELS[name], True, TEXT_COL)
            surface.blit(t, (r.x + 26, r.centery - t.get_height() // 2))
            ry += 34
        return y + ch

    def _draw_model(self, surface: pygame.Surface, w: int, y: int) -> int:
        cx = PAD
        cw = w - PAD * 2
        ch = 58
        pygame.draw.rect(surface, CARD_BG, pygame.Rect(cx, y, cw, ch), border_radius=RADIUS)
        ht = self._font_h.render("Model", True, MUTED)
        surface.blit(ht, (cx + 10, y + 8))
        models = _MODELS[self._provider]
        model  = models[self._model_idx]
        aw     = 26
        prev_r = pygame.Rect(cx + 10, y + 24, aw, aw)
        next_r = pygame.Rect(cx + cw - 10 - aw, y + 24, aw, aw)
        self._model_prev = prev_r
        self._model_next = next_r
        pygame.draw.rect(surface, UNSEL_COL, prev_r, border_radius=5)
        pygame.draw.rect(surface, UNSEL_COL, next_r, border_radius=5)
        pi = self._icon_prev
        ni = self._icon_next
        surface.blit(pi, (prev_r.centerx - pi.get_width() // 2,
                          prev_r.centery - pi.get_height() // 2))
        surface.blit(ni, (next_r.centerx - ni.get_width() // 2,
                          next_r.centery - ni.get_height() // 2))
        mt = self._font_sm.render(model, True, TEXT_COL)
        surface.blit(mt, (cx + cw // 2 - mt.get_width() // 2,
                          y + 24 + aw // 2 - mt.get_height() // 2))
        return y + ch

    def _draw_display(self, surface: pygame.Surface, w: int, y: int) -> int:
        cx = PAD
        cw = w - PAD * 2
        ch = 52
        pygame.draw.rect(surface, CARD_BG, pygame.Rect(cx, y, cw, ch), border_radius=RADIUS)
        ht = self._font_h.render("Display", True, MUTED)
        surface.blit(ht, (cx + 10, y + 8))
        tg = pygame.Rect(cx + cw - 10 - 46, y + 20, 46, 24)
        self._toggle_rect = tg
        pygame.draw.rect(surface, TOGGLE_ON if self._always_on_top else TOGGLE_OFF,
                         tg, border_radius=12)
        kx = tg.right - 14 if self._always_on_top else tg.left + 2
        pygame.draw.circle(surface, (220, 225, 240), (kx + 10, tg.centery), 9)
        lbl = self._font.render("Always on top", True, TEXT_COL)
        surface.blit(lbl, (cx + 10, tg.centery - lbl.get_height() // 2))
        return y + ch

    def _draw_mcp(self, surface: pygame.Surface, w: int, y: int) -> int:
        cx  = PAD
        cw  = w - PAD * 2
        ROW = 30   # px per server row
        FORM_H = 162  # inline edit form height (includes headers field)

        n_rows  = len(self._mcp_servers)
        form_open = self._mcp_edit_idx is not None
        ch = 26 + n_rows * ROW + 32 + (FORM_H if form_open else 0) + 8

        pygame.draw.rect(surface, CARD_BG, pygame.Rect(cx, y, cw, ch), border_radius=RADIUS)

        # ── header: "MCP Servers" + [+] button ──────────────────────────────
        ht = self._font_h.render("MCP Servers", True, MUTED)
        surface.blit(ht, (cx + 10, y + 8))
        add_r = pygame.Rect(cx + cw - 36, y + 4, 28, 20)
        self._mcp_add_rect = add_r
        pygame.draw.rect(surface, ADD_COL, add_r, border_radius=5)
        plus = self._font_bold.render("+", True, (220, 255, 220))
        surface.blit(plus, (add_r.centerx - plus.get_width() // 2,
                             add_r.centery - plus.get_height() // 2))

        # ── server rows ──────────────────────────────────────────────────────
        self._mcp_row_toggle = []
        self._mcp_row_edit   = []
        self._mcp_row_del    = []
        ry = y + 26

        for i, srv in enumerate(self._mcp_servers):
            enabled = srv.get("enabled", False)
            name    = srv.get("name", "")
            url     = srv.get("url",  "")

            # toggle dot
            dot_r = pygame.Rect(cx + 10, ry + ROW // 2 - 6, 14, 14)
            self._mcp_row_toggle.append(dot_r)
            dot_col = (80, 200, 120) if enabled else (80, 80, 110)
            pygame.draw.circle(surface, dot_col, dot_r.center, 6, 0 if enabled else 2)

            # headers badge (🔑 N) if server has custom headers
            hdrs = srv.get("headers") or {}
            badge_w = 0
            if hdrs:
                badge_txt = self._font_sm.render(f"\U0001f511{len(hdrs)}", True, (140, 220, 160))
                badge_w = badge_txt.get_width() + 6
                surface.blit(badge_txt, (cx + cw - 14 - 22 - 26 - 4 - badge_w + 3,
                                         ry + ROW // 2 - badge_txt.get_height() // 2))

            # name + url text
            max_text_w = cw - 10 - 14 - 8 - 54 - badge_w  # leave room for buttons + badge
            name_surf = self._font_sm.render(name, True, TEXT_COL)
            url_short = url.replace("http://", "").replace("https://", "")
            url_surf  = self._font_sm.render(url_short, True, MUTED)
            tx = cx + 10 + 14 + 8
            surface.blit(name_surf, (tx, ry + 4))
            if url_surf.get_width() < max_text_w:
                surface.blit(url_surf, (tx, ry + 4 + name_surf.get_height()))

            # edit + delete buttons
            btn_y   = ry + ROW // 2 - 10
            del_r   = pygame.Rect(cx + cw - 14 - 22, btn_y, 22, 20)
            edit_r  = pygame.Rect(cx + cw - 14 - 22 - 26, btn_y, 22, 20)
            self._mcp_row_del.append(del_r)
            self._mcp_row_edit.append(edit_r)
            pygame.draw.rect(surface, EDIT_COL, edit_r, border_radius=4)
            pygame.draw.rect(surface, DEL_COL,  del_r,  border_radius=4)
            surface.blit(self._icon_edit, (edit_r.centerx - self._icon_edit.get_width() // 2,
                                           edit_r.centery - self._icon_edit.get_height() // 2))
            surface.blit(self._icon_del,  (del_r.centerx  - self._icon_del.get_width()  // 2,
                                           del_r.centery  - self._icon_del.get_height()  // 2))

            # divider
            if i < n_rows - 1:
                pygame.draw.line(surface, (40, 44, 68),
                                 (cx + 10, ry + ROW - 1), (cx + cw - 10, ry + ROW - 1))
            ry += ROW

        # empty state
        if n_rows == 0:
            empty = self._font_sm.render("ยังไม่มี MCP server — กด + เพื่อเพิ่ม", True, MUTED)
            surface.blit(empty, (cx + cw // 2 - empty.get_width() // 2, ry + 4))
            ry += 26

        # ── inline edit form ─────────────────────────────────────────────────
        self._mcp_form_preset_rects = []
        self._mcp_form_name_r    = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_url_r     = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_headers_r = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_save_r    = pygame.Rect(0, 0, 1, 1)
        self._mcp_form_cancel_r  = pygame.Rect(0, 0, 1, 1)

        if form_open:
            fy = ry + 4
            fw = cw - 20
            fx = cx + 10

            # form background
            pygame.draw.rect(surface, (32, 36, 62),
                             pygame.Rect(fx - 4, fy - 4, fw + 8, FORM_H + 4), border_radius=6)

            # preset chips row
            chip_w = (fw - (len(_MCP_PRESETS) - 1) * 4) // len(_MCP_PRESETS)
            for i, (label, url) in enumerate(_MCP_PRESETS):
                cr = pygame.Rect(fx + i * (chip_w + 4), fy, chip_w, 20)
                self._mcp_form_preset_rects.append(cr)
                active = (url == self._mcp_edit_url) and url
                pygame.draw.rect(surface, SEL_COL if active else UNSEL_COL, cr, border_radius=4)
                ct = self._font_sm.render(label, True, TEXT_COL)
                surface.blit(ct, (cr.centerx - ct.get_width() // 2,
                                   cr.centery - ct.get_height() // 2))
            fy += 26

            # Name input
            nl = self._font_sm.render("ชื่อ", True, MUTED)
            surface.blit(nl, (fx, fy))
            fy += nl.get_height() + 2
            name_r = pygame.Rect(fx, fy, fw, 24)
            self._mcp_form_name_r = name_r
            bg = INPUT_FOC if self._mcp_input_focus == "name" else INPUT_BG
            pygame.draw.rect(surface, bg, name_r, border_radius=5)
            pygame.draw.rect(surface, SEL_COL if self._mcp_input_focus == "name" else (50,55,90),
                             name_r, 1, border_radius=5)
            nt = self._font_sm.render(self._mcp_edit_name, True, TEXT_COL)
            surface.blit(nt, (name_r.x + 5, name_r.centery - nt.get_height() // 2))
            if self._mcp_input_focus == "name" and self._cursor_tick < 30:
                cx2 = name_r.x + 5 + nt.get_width() + 1
                pygame.draw.line(surface, TEXT_COL, (cx2, name_r.y + 4), (cx2, name_r.bottom - 4))
            fy += 28

            # URL input
            ul = self._font_sm.render("URL", True, MUTED)
            surface.blit(ul, (fx, fy))
            fy += ul.get_height() + 2
            url_r = pygame.Rect(fx, fy, fw, 24)
            self._mcp_form_url_r = url_r
            bg2 = INPUT_FOC if self._mcp_input_focus == "url" else INPUT_BG
            pygame.draw.rect(surface, bg2, url_r, border_radius=5)
            pygame.draw.rect(surface, SEL_COL if self._mcp_input_focus == "url" else (50,55,90),
                             url_r, 1, border_radius=5)
            max_uw = url_r.width - 10
            du = self._mcp_edit_url
            us = self._font_sm.render(du, True, TEXT_COL)
            while us.get_width() > max_uw and du:
                du = du[1:]
                us = self._font_sm.render("…" + du, True, TEXT_COL)
            if du != self._mcp_edit_url:
                us = self._font_sm.render("…" + du, True, TEXT_COL)
            surface.blit(us, (url_r.x + 5, url_r.centery - us.get_height() // 2))
            if self._mcp_input_focus == "url" and self._cursor_tick < 30:
                cx3 = url_r.x + 5 + us.get_width() + 1
                pygame.draw.line(surface, TEXT_COL, (cx3, url_r.y + 4), (cx3, url_r.bottom - 4))
            fy += 28

            # Headers input
            hl = self._font_sm.render("Headers (JSON)", True, MUTED)
            surface.blit(hl, (fx, fy))
            fy += hl.get_height() + 2
            hdr_r = pygame.Rect(fx, fy, fw, 24)
            self._mcp_form_headers_r = hdr_r
            bg3 = INPUT_FOC if self._mcp_input_focus == "headers" else INPUT_BG
            pygame.draw.rect(surface, bg3, hdr_r, border_radius=5)
            pygame.draw.rect(surface, SEL_COL if self._mcp_input_focus == "headers" else (50, 55, 90),
                             hdr_r, 1, border_radius=5)
            max_hw = hdr_r.width - 10
            dh = self._mcp_edit_headers
            if dh:
                hs = self._font_sm.render(dh, True, TEXT_COL)
                while hs.get_width() > max_hw and dh:
                    dh = dh[1:]
                    hs = self._font_sm.render("\u2026" + dh, True, TEXT_COL)
                if dh != self._mcp_edit_headers:
                    hs = self._font_sm.render("\u2026" + dh, True, TEXT_COL)
            else:
                hs = self._font_sm.render('{"Authorization": "Bearer ..."}', True, (60, 65, 100))
            surface.blit(hs, (hdr_r.x + 5, hdr_r.centery - hs.get_height() // 2))
            if self._mcp_input_focus == "headers" and self._mcp_edit_headers and self._cursor_tick < 30:
                cx4 = hdr_r.x + 5 + self._font_sm.render(self._mcp_edit_headers, True, TEXT_COL).get_width() + 1
                cx4 = min(cx4, hdr_r.right - 6)
                pygame.draw.line(surface, TEXT_COL, (cx4, hdr_r.y + 4), (cx4, hdr_r.bottom - 4))
            fy += 28

            # Save / Cancel buttons
            btn_w2 = (fw - 6) // 2
            save_r   = pygame.Rect(fx, fy, btn_w2, 22)
            cancel_r = pygame.Rect(fx + btn_w2 + 6, fy, btn_w2, 22)
            self._mcp_form_save_r   = save_r
            self._mcp_form_cancel_r = cancel_r
            pygame.draw.rect(surface, ADD_COL,   save_r,   border_radius=5)
            pygame.draw.rect(surface, UNSEL_COL, cancel_r, border_radius=5)
            sv = self._font_sm.render("บันทึก", True, (220, 255, 220))
            cn = self._font_sm.render("ยกเลิก", True, TEXT_COL)
            surface.blit(sv, (save_r.centerx   - sv.get_width() // 2,
                               save_r.centery   - sv.get_height() // 2))
            surface.blit(cn, (cancel_r.centerx - cn.get_width() // 2,
                               cancel_r.centery - cn.get_height() // 2))

        return y + ch

    def _draw_kb(self, surface: pygame.Surface, w: int, y: int) -> int:
        cx  = PAD
        cw  = w - PAD * 2
        ROW = 28
        n   = len(self._kb_docs)
        ch  = 26 + max(n, 1) * ROW + 34 + 10
        pygame.draw.rect(surface, CARD_BG, pygame.Rect(cx, y, cw, ch), border_radius=RADIUS)

        # header
        ht = self._font_h.render("Knowledge Base", True, MUTED)
        surface.blit(ht, (cx + 10, y + 8))

        # status flash
        if self._kb_status_tick > 0:
            st = self._font_sm.render(self._kb_status, True, (120, 210, 140))
            surface.blit(st, (cx + cw - 10 - st.get_width(), y + 8))

        # document list
        self._kb_del_rects = []
        ry = y + 26
        if n == 0:
            empty = self._font_sm.render("ยังไม่มีเอกสาร", True, MUTED)
            surface.blit(empty, (cx + 14, ry + 6))
            ry += ROW
        else:
            for doc in self._kb_docs:
                name   = doc.get("source", doc.get("doc_id", "?"))
                chunks = doc.get("chunk_count", 0)
                nt = self._font_sm.render(name[:30], True, TEXT_COL)
                ct = self._font_sm.render(f"{chunks} chunks", True, MUTED)
                surface.blit(nt, (cx + 14, ry + 4))
                surface.blit(ct, (cx + 14 + nt.get_width() + 8, ry + 4))
                del_r = pygame.Rect(cx + cw - 14 - 22, ry + ROW // 2 - 10, 22, 20)
                self._kb_del_rects.append(del_r)
                pygame.draw.rect(surface, DEL_COL, del_r, border_radius=4)
                surface.blit(self._icon_del, (del_r.centerx - self._icon_del.get_width() // 2,
                                              del_r.centery - self._icon_del.get_height() // 2))
                ry += ROW

        # path input + add button
        ry += 4
        btn_w2 = 52
        path_r = pygame.Rect(cx + 10, ry, cw - 20 - btn_w2 - 4, 24)
        add_r  = pygame.Rect(path_r.right + 4, ry, btn_w2, 24)
        self._kb_path_rect = path_r
        self._kb_add_rect  = add_r
        bg = INPUT_FOC if self._kb_path_focused else INPUT_BG
        pygame.draw.rect(surface, bg, path_r, border_radius=5)
        pygame.draw.rect(surface, SEL_COL if self._kb_path_focused else (50, 55, 90),
                         path_r, 1, border_radius=5)
        hint = self._kb_path_buf if self._kb_path_buf else "~/path/to/file.pdf"
        col  = TEXT_COL if self._kb_path_buf else MUTED
        pt = self._font_sm.render(hint, True, col)
        # clip to fit
        max_pw = path_r.width - 10
        clip_surf = pygame.Surface((max_pw, pt.get_height()), pygame.SRCALPHA)
        clip_surf.blit(pt, (0, 0))
        surface.blit(clip_surf, (path_r.x + 5, path_r.centery - pt.get_height() // 2))
        if self._kb_path_focused and self._cursor_tick < 30:
            cxp = path_r.x + 5 + min(pt.get_width(), max_pw) + 1
            pygame.draw.line(surface, TEXT_COL,
                             (cxp, path_r.y + 4), (cxp, path_r.bottom - 4))
        pygame.draw.rect(surface, ADD_COL, add_r, border_radius=5)
        at = self._font_sm.render("เพิ่ม", True, (220, 255, 220))
        surface.blit(at, (add_r.centerx - at.get_width() // 2,
                           add_r.centery - at.get_height() // 2))

        return y + ch

    def _draw_danger(self, surface: pygame.Surface, w: int, y: int) -> int:
        cx = PAD
        cw = w - PAD * 2
        ch = 52
        pygame.draw.rect(surface, (35, 22, 22), pygame.Rect(cx, y, cw, ch), border_radius=RADIUS)
        ht = self._font_h.render("Danger Zone", True, (180, 80, 80))
        surface.blit(ht, (cx + 10, y + 8))

        btn_w, btn_h = 120, 26
        btn_r = pygame.Rect(cx + cw - btn_w - 10, y + (ch - btn_h) // 2, btn_w, btn_h)
        self._clear_rect = btn_r
        btn_col = (200, 70, 70) if self._clear_hov else (150, 45, 45)
        pygame.draw.rect(surface, btn_col, btn_r, border_radius=6)
        lbl = self._font_sm.render("ล้างประวัติแชท", True, (240, 220, 220))
        surface.blit(lbl, (btn_r.centerx - lbl.get_width() // 2,
                           btn_r.centery - lbl.get_height() // 2))

        if self._clear_flash > 0:
            ok = self._font_sm.render("ล้างแล้ว!", True, (220, 100, 100))
            surface.blit(ok, (cx + 10, btn_r.centery - ok.get_height() // 2))
        return y + ch

    def _draw_save(self, surface: pygame.Surface) -> None:
        w, _ = self._last_size
        if self._saved_flash > 0:
            ic  = self._icon_check
            msg = self._font_bold.render("บันทึกแล้ว!", True, (100, 220, 130))
            my  = self._save_rect.centery
            surface.blit(ic,  (PAD, my - ic.get_height() // 2))
            surface.blit(msg, (PAD + ic.get_width() + 4, my - msg.get_height() // 2))
        col = SAVE_HOV if self._save_hov else SAVE_BG
        pygame.draw.rect(surface, col, self._save_rect, border_radius=8)
        st = self._font_bold.render("บันทึก", True, (240, 250, 240))
        surface.blit(st, (self._save_rect.centerx - st.get_width() // 2,
                          self._save_rect.centery - st.get_height() // 2))
