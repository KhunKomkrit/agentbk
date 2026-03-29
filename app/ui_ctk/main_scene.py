"""MainScene — avatar + Chat / Settings buttons."""
from __future__ import annotations

import re
import customtkinter as ctk

from app.ui_ctk.scene_manager import BaseScene
from app.ui_ctk.avatar_canvas import AvatarCanvas
from app.ui_ctk import font_manager
from app.avatar.renderer import AvatarState


_STATE_INFO: dict[AvatarState, tuple[str, str]] = {
    AvatarState.IDLE:     ("idle",      "#46B446"),
    AvatarState.THINKING: ("thinking…", "#B4B446"),
    AvatarState.TALKING:  ("talking",   "#4682B4"),
    AvatarState.ERROR:    ("error",     "#C84646"),
    AvatarState.LOADING:  ("loading…",  "#7882FF"),
}


class MainScene(BaseScene):
    def __init__(self, parent: ctk.CTkFrame, router=None) -> None:
        self._router = router

        # Scene frame
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")

        # ── Avatar card ──────────────────────────────────────────────────
        self._card = ctk.CTkFrame(
            self.frame, corner_radius=14,
            fg_color=("#16162A", "#16162A"),
        )
        self._card.pack(fill="both", expand=True, padx=12, pady=(8, 6))

        # Avatar widget (128px pixel art)
        self._avatar = AvatarCanvas(
            self._card, size=128,
            fg_color="transparent",
        )
        self._avatar.pack(expand=True, pady=(24, 4))

        # State badge label
        self._state_label = ctk.CTkLabel(
            self._card, text="loading…",
            font=font_manager.ctk_font(11),
            text_color=("#7882FF", "#7882FF"),
        )
        self._state_label.pack(pady=(0, 16))

        # ── Loading progress widgets ──────────────────────────────────────
        self._progress_frame = ctk.CTkFrame(
            self._card, corner_radius=0, fg_color="transparent",
        )
        self._progress_frame.pack(fill="x", padx=20, pady=(0, 8))

        self._progress_bar = ctk.CTkProgressBar(
            self._progress_frame, height=4, corner_radius=2,
            fg_color=("#2A2A4A", "#2A2A4A"),
            progress_color=("#7882FF", "#7882FF"),
        )
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", pady=(0, 4))

        self._progress_label = ctk.CTkLabel(
            self._progress_frame, text="",
            font=font_manager.ctk_font(10),
            text_color=("#606080", "#606080"),
            wraplength=260,
        )
        self._progress_label.pack(fill="x")

        # ── Action buttons ────────────────────────────────────────────────
        self._btn_frame = ctk.CTkFrame(
            self.frame, corner_radius=0, fg_color="transparent",
        )
        self._btn_frame.pack(fill="x", padx=12, pady=(0, 12))
        self._btn_frame.columnconfigure((0, 1), weight=1)

        self._btn_chat = ctk.CTkButton(
            self._btn_frame, text="💬  Chat",
            font=font_manager.ctk_font(13),
            height=38, corner_radius=8,
            fg_color=("#3C5CAA", "#3C5CAA"),
            hover_color=("#5070CC", "#5070CC"),
            state="disabled",
            command=self._go_chat,
        )
        self._btn_chat.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self._btn_settings = ctk.CTkButton(
            self._btn_frame, text="⚙  Settings",
            font=font_manager.ctk_font(13),
            height=38, corner_radius=8,
            fg_color=("#3A3A5C", "#3A3A5C"),
            hover_color=("#505080", "#505080"),
            state="disabled",
            command=self._go_settings,
        )
        self._btn_settings.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # Internal state
        self._init_complete = False
        self._ollama_frac = 0.0

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        self._avatar.start()
        self._poll()

    def on_exit(self) -> None:
        self._avatar.stop()

    # ── Queue polling ────────────────────────────────────────────────────────

    def _poll(self) -> None:
        """Poll AgentRouter queue for init progress. Runs via after()."""
        if not self._init_complete and self._router:
            # Check is_ready flag
            if self._router.is_ready:
                self._mark_ready()
            else:
                # Drain progress chunks
                while True:
                    try:
                        chunk = self._router.result_queue.get_nowait()
                        if chunk.kind == "init_progress":
                            self._progress_label.configure(text=chunk.text)
                        elif chunk.kind == "ollama_progress":
                            self._progress_label.configure(text=chunk.text)
                            m = re.search(r"(\d+)%", chunk.text)
                            self._ollama_frac = int(m.group(1)) / 100.0 if m else 0.0
                            self._progress_bar.set(self._ollama_frac)
                    except Exception:
                        break
                self._avatar.state = AvatarState.LOADING
                state_text, state_color = _STATE_INFO[AvatarState.LOADING]
                self._state_label.configure(text=state_text, text_color=state_color)
                self.frame.after(200, self._poll)
        else:
            self._mark_ready()

    def _mark_ready(self) -> None:
        if self._init_complete:
            return
        self._init_complete = True
        self._avatar.state = AvatarState.IDLE
        state_text, state_color = _STATE_INFO[AvatarState.IDLE]
        self._state_label.configure(text=state_text, text_color=state_color)
        self._progress_frame.pack_forget()
        self._btn_chat.configure(state="normal")
        self._btn_settings.configure(state="normal")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_chat(self) -> None:
        from app.ui_ctk.chat_scene import ChatScene
        self.manager.push(ChatScene(self.frame.master, self._router, self._avatar))

    def _go_settings(self) -> None:
        from app.ui_ctk.settings_scene import SettingsScene
        self.manager.push(SettingsScene(self.frame.master, self._router))

    # ── External avatar state update (called by queue_poller) ─────────────────

    def set_avatar_state(self, state: AvatarState) -> None:
        self._avatar.state = state
        text, color = _STATE_INFO.get(state, ("", "#FFFFFF"))
        self._state_label.configure(text=text, text_color=color)
