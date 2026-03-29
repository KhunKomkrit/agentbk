"""ChatScene — message history, text input, streaming, attachments, STT."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.ui_ctk.scene_manager import BaseScene
from app.ui_ctk import font_manager
from app.avatar.renderer import AvatarState

if TYPE_CHECKING:
    from app.ui_ctk.avatar_canvas import AvatarCanvas
    from app.agent.router import AgentRouter

_WELCOME = "สวัสดี! ฉันคือ AgentBK พิมพ์อะไรก็ได้เลยนะ :)"

# Colors
_BG_USER = ("#3C5CAA", "#3C5CAA")
_BG_BOT  = ("#252540", "#252540")
_FG_TEXT = ("#D7DCFF", "#D7DCFF")
_FG_HINT = ("#606090", "#606090")


class _MsgBubble(ctk.CTkFrame):
    """Single chat bubble widget."""

    def __init__(self, parent, text: str, is_user: bool, max_wrap: int = 260) -> None:
        color = _BG_USER if is_user else _BG_BOT
        anchor = "e" if is_user else "w"
        super().__init__(parent, corner_radius=10, fg_color=color)

        self._label = ctk.CTkLabel(
            self, text=text,
            font=font_manager.ctk_font(13),
            text_color=_FG_TEXT,
            wraplength=max_wrap,
            justify="left",
            anchor="w",
        )
        self._label.pack(padx=10, pady=(6, 7), fill="x")

    def update_text(self, text: str) -> None:
        self._label.configure(text=text)


class ChatScene(BaseScene):
    def __init__(self, parent: ctk.CTkFrame, router: "AgentRouter | None",
                 avatar: "AvatarCanvas | None" = None) -> None:
        self._router  = router
        self._avatar  = avatar
        self._is_streaming   = False
        self._streaming_bubble: _MsgBubble | None = None
        self._streaming_text = ""
        self._tool_indicator = ""
        self._pending_attachment = None
        self._toast = ""
        self._is_recording = False
        self._listener = None

        # Scene root frame
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")

        # ── Header ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(
            self.frame, height=48, corner_radius=0,
            fg_color=("#16162A", "#16162A"),
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkButton(
            header, text="← Back",
            font=font_manager.ctk_font(12),
            width=64, height=28, corner_radius=6,
            fg_color=("#2C2C50", "#2C2C50"),
            hover_color=("#404070", "#404070"),
            command=self._go_back,
        ).pack(side="left", padx=8, pady=10)

        ctk.CTkButton(
            header, text="＋ New",
            font=font_manager.ctk_font(12),
            width=60, height=28, corner_radius=6,
            fg_color=("#2C2C50", "#2C2C50"),
            hover_color=("#404070", "#404070"),
            command=self._new_chat,
        ).pack(side="right", padx=8, pady=10)

        ctk.CTkLabel(
            header, text="Chat",
            font=font_manager.ctk_font(13, bold=True),
            text_color=("#A0B0DC", "#A0B0DC"),
        ).pack(side="left", expand=True)

        # ── Tool indicator label ───────────────────────────────────────────
        self._tool_label = ctk.CTkLabel(
            self.frame, text="",
            font=font_manager.ctk_font(11),
            text_color=("#6070B0", "#6070B0"),
            height=16,
        )
        self._tool_label.pack(fill="x", padx=12)

        # ── Message history (scrollable) ──────────────────────────────────
        self._history_frame = ctk.CTkScrollableFrame(
            self.frame, corner_radius=0,
            fg_color=("#1A1A30", "#1A1A30"),
            scrollbar_button_color=("#303050", "#303050"),
            scrollbar_button_hover_color=("#404070", "#404070"),
        )
        self._history_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._history_frame.columnconfigure(0, weight=1)

        # ── Toast ──────────────────────────────────────────────────────────
        self._toast_label = ctk.CTkLabel(
            self.frame, text="",
            font=font_manager.ctk_font(11),
            text_color=("#8090C0", "#8090C0"),
            height=16,
        )
        self._toast_label.pack(fill="x", padx=12)

        # ── Attachment preview ─────────────────────────────────────────────
        self._attach_bar = ctk.CTkFrame(
            self.frame, height=0, corner_radius=6,
            fg_color=("#20203A", "#20203A"),
        )
        # Not packed yet — shown only when attachment present

        self._attach_label = ctk.CTkLabel(
            self._attach_bar, text="",
            font=font_manager.ctk_font(11),
            text_color=("#A0B0D0", "#A0B0D0"),
        )
        self._attach_label.pack(side="left", padx=8, pady=4, expand=True, fill="x")

        ctk.CTkButton(
            self._attach_bar, text="✕",
            width=24, height=20, corner_radius=4,
            font=font_manager.ctk_font(11),
            fg_color="transparent",
            hover_color=("#602020", "#602020"),
            text_color=("#C07070", "#C07070"),
            command=self._dismiss_attachment,
        ).pack(side="right", padx=4, pady=4)

        # ── Input row ─────────────────────────────────────────────────────
        input_row = ctk.CTkFrame(
            self.frame, corner_radius=0,
            fg_color=("#16162A", "#16162A"),
        )
        input_row.pack(fill="x", side="bottom", padx=0, pady=0)

        ctk.CTkButton(
            input_row, text="📎",
            width=34, height=34, corner_radius=6,
            font=font_manager.ctk_font(14),
            fg_color=("#2C2C50", "#2C2C50"),
            hover_color=("#404070", "#404070"),
            command=self._open_file_dialog,
        ).pack(side="left", padx=(8, 0), pady=7)

        self._mic_btn = ctk.CTkButton(
            input_row, text="🎤",
            width=34, height=34, corner_radius=6,
            font=font_manager.ctk_font(14),
            fg_color=("#2C2C50", "#2C2C50"),
            hover_color=("#404070", "#404070"),
            command=self._toggle_mic,
        )
        self._mic_btn.pack(side="left", padx=(4, 0), pady=7)

        self._input_box = ctk.CTkTextbox(
            input_row, height=34, corner_radius=6,
            font=font_manager.ctk_font(13),
            fg_color=("#1E1E38", "#1E1E38"),
            border_color=("#3C4680", "#3C4680"),
            border_width=1,
            wrap="word",
        )
        self._input_box.pack(side="left", fill="x", expand=True, padx=6, pady=7)
        self._input_box.bind("<Return>",       self._on_return)
        self._input_box.bind("<Shift-Return>", lambda e: None)  # allow actual newline

        self._send_btn = ctk.CTkButton(
            input_row, text="▶",
            width=34, height=34, corner_radius=6,
            font=font_manager.ctk_font(14),
            fg_color=("#3C6CC8", "#3C6CC8"),
            hover_color=("#5080E0", "#5080E0"),
            command=self._submit,
        )
        self._send_btn.pack(side="right", padx=(0, 8), pady=7)

        # Bubble list
        self._bubbles: list[_MsgBubble] = []

        # Load history on init
        self._load_history()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        if self._avatar:
            self._avatar.state = AvatarState.IDLE
        if not self._is_streaming:
            self._load_history()
        self._input_box.focus_set()

    def on_exit(self) -> None:
        if self._is_recording:
            self._stop_listening()

    # ── History ────────────────────────────────────────────────────────────────

    def _load_history(self) -> None:
        for b in self._bubbles:
            b.destroy()
        self._bubbles.clear()

        msgs: list[tuple[bool, str]] = []
        if self._router:
            for m in self._router._memory.messages:
                if m.get("role") not in ("user", "assistant"):
                    continue
                content = m.get("content", "")
                if isinstance(content, list):
                    text = " ".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                else:
                    text = content
                if text.strip():
                    msgs.append((m["role"] == "user", text))

        if not msgs:
            msgs = [(False, _WELCOME)]

        for is_user, text in msgs:
            self._add_bubble(text, is_user)

        self._scroll_to_bottom()

    def _add_bubble(self, text: str, is_user: bool) -> _MsgBubble:
        bubble = _MsgBubble(self._history_frame, text, is_user)
        side = "e" if is_user else "w"
        # Pack with alignment
        container = ctk.CTkFrame(
            self._history_frame, fg_color="transparent", corner_radius=0,
        )
        container.pack(fill="x", padx=8, pady=3)
        bubble = _MsgBubble(container, text, is_user)
        if is_user:
            bubble.pack(side="right", anchor="e", padx=(40, 0))
        else:
            bubble.pack(side="left", anchor="w", padx=(0, 40))
        self._bubbles.append(bubble)
        return bubble

    def _new_chat(self) -> None:
        if self._is_streaming:
            return
        if self._router:
            self._router.clear_history()  # type: ignore[attr-defined]
        self._load_history()

    # ── Submit / Streaming ────────────────────────────────────────────────────

    def _on_return(self, event) -> str:
        if not event.state & 1:  # Shift not held
            self._submit()
            return "break"
        return ""

    def _submit(self) -> None:
        if self._is_streaming or not self._router:
            return
        text = self._input_box.get("1.0", "end").strip()
        if not text and not self._pending_attachment:
            return

        self._input_box.delete("1.0", "end")

        # Add user bubble
        self._add_bubble(text or "[attachment]", is_user=True)
        self._scroll_to_bottom()

        # Bot placeholder
        bot_bubble = self._add_bubble("…", is_user=False)
        self._streaming_bubble = bot_bubble
        self._streaming_text = ""
        self._scroll_to_bottom()

        # Update avatar
        if self._avatar:
            self._avatar.state = AvatarState.THINKING

        self._is_streaming = True
        self._send_btn.configure(state="disabled")

        # Submit to router
        attach = self._pending_attachment
        self._pending_attachment = None
        self._hide_attach_bar()

        self._router.start_stream(text, attachment=attach)
        self._poll_stream()

    def _poll_stream(self) -> None:
        """Poll result_queue every 50ms while streaming."""
        if not self._is_streaming or not self._router:
            return
        try:
            while True:
                chunk = self._router.result_queue.get_nowait()
                if chunk.kind == "chunk":
                    self._streaming_text += chunk.text
                    if self._streaming_bubble:
                        self._streaming_bubble.update_text(self._streaming_text)
                    if self._avatar:
                        self._avatar.state = AvatarState.TALKING
                elif chunk.kind == "tool_use":
                    self._tool_label.configure(text=f"🔧 {chunk.text}")
                    if self._avatar:
                        self._avatar.state = AvatarState.THINKING
                elif chunk.kind == "done":
                    self._finish_streaming()
                    return
                elif chunk.kind == "error":
                    if self._streaming_bubble:
                        self._streaming_bubble.update_text(f"⚠ {chunk.text}")
                    self._finish_streaming(error=True)
                    return
        except Exception:
            pass
        self.frame.after(50, self._poll_stream)

    def _finish_streaming(self, error: bool = False) -> None:
        self._is_streaming = False
        self._streaming_bubble = None
        self._tool_label.configure(text="")
        self._send_btn.configure(state="normal")
        if self._avatar:
            self._avatar.state = AvatarState.ERROR if error else AvatarState.IDLE
        self._scroll_to_bottom()

    # ── Attachment ────────────────────────────────────────────────────────────

    def _open_file_dialog(self) -> None:
        import tkinter.filedialog as fd
        path = fd.askopenfilename(
            title="Select file",
            filetypes=[
                ("All supported", "*.pdf *.txt *.md *.png *.jpg *.jpeg *.gif *.webp"),
                ("PDF", "*.pdf"),
                ("Text", "*.txt *.md"),
                ("Image", "*.png *.jpg *.jpeg *.gif *.webp"),
            ],
        )
        if path:
            self._load_attachment(path)

    def _load_attachment(self, path: str) -> None:
        def _work() -> None:
            try:
                from app.agent.attachment import process_file
                result = process_file(path)
                self.frame.after(0, lambda: self._set_attachment(result))
            except Exception as e:
                self.frame.after(0, lambda: self._show_toast(f"⚠ {e}"))

        threading.Thread(target=_work, daemon=True).start()

    def _set_attachment(self, result) -> None:
        self._pending_attachment = result
        import os
        name = os.path.basename(result.path) if hasattr(result, "path") else str(result)
        self._attach_label.configure(text=f"📎 {name}")
        self._attach_bar.pack(fill="x", padx=8, pady=(0, 2))

    def _dismiss_attachment(self) -> None:
        self._pending_attachment = None
        self._hide_attach_bar()

    def _hide_attach_bar(self) -> None:
        self._attach_bar.pack_forget()

    # ── Mic / STT ─────────────────────────────────────────────────────────────

    def _toggle_mic(self) -> None:
        if not self._is_recording:
            self._start_listening()
        else:
            self._stop_listening()

    def _start_listening(self) -> None:
        try:
            from app.stt.listener import SpeechListener
            self._listener = SpeechListener()
        except Exception:
            self._show_toast("⚠ STT not available")
            return
        self._is_recording = True
        self._mic_btn.configure(text="⏹", fg_color=("#7A2020", "#7A2020"))

        def _work() -> None:
            try:
                text = self._listener.listen()
                self.frame.after(0, lambda: self._on_stt_result(text))
            except Exception as e:
                self.frame.after(0, lambda: self._show_toast(f"⚠ {e}"))
            finally:
                self.frame.after(0, self._stop_listening)

        threading.Thread(target=_work, daemon=True).start()

    def _stop_listening(self) -> None:
        self._is_recording = False
        self._mic_btn.configure(text="🎤", fg_color=("#2C2C50", "#2C2C50"))

    def _on_stt_result(self, text: str) -> None:
        if text:
            self._input_box.insert("end", text)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _go_back(self) -> None:
        self.manager.pop()

    def _show_toast(self, msg: str, ms: int = 3000) -> None:
        self._toast_label.configure(text=msg)
        self.frame.after(ms, lambda: self._toast_label.configure(text=""))

    def _scroll_to_bottom(self) -> None:
        self.frame.after(50, lambda: self._history_frame._parent_canvas.yview_moveto(1.0))
