"""AppWindow — borderless, always-on-top, draggable, resizable CTk root window."""
from __future__ import annotations

import customtkinter as ctk

# Window constraints
_MIN_W, _MIN_H = 320, 400
_MAX_W, _MAX_H = 700, 900
_DEFAULT_W, _DEFAULT_H = 360, 560
_GRIP_SIZE = 18        # bottom-right resize grip
_TITLE_BAR_H = 32      # drag area height


class AppWindow(ctk.CTk):
    """Root window: borderless, draggable titlebar, bottom-right resize grip."""

    def __init__(self, always_on_top: bool = True) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.overrideredirect(True)          # borderless
        self.wm_attributes("-topmost", always_on_top)
        self.resizable(False, False)         # we manage resize manually

        # Center on screen
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - _DEFAULT_W) // 2
        y = (sh - _DEFAULT_H) // 2
        self.geometry(f"{_DEFAULT_W}x{_DEFAULT_H}+{x}+{y}")

        self._always_on_top = always_on_top
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_win_x = 0
        self._drag_win_y = 0
        self._resizing = False
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = _DEFAULT_W
        self._resize_start_h = _DEFAULT_H

        # ── Layout ──────────────────────────────────────────────
        # Outer frame for rounded corners + shadow illusion
        self._outer = ctk.CTkFrame(self, corner_radius=14, fg_color=("#1A1A2E", "#1A1A2E"))
        self._outer.pack(fill="both", expand=True, padx=0, pady=0)

        # Drag title bar
        self._titlebar = ctk.CTkFrame(
            self._outer, height=_TITLE_BAR_H, corner_radius=0,
            fg_color=("#16162A", "#16162A"),
        )
        self._titlebar.pack(fill="x", side="top")
        self._titlebar.pack_propagate(False)

        # Title label
        self._title_label = ctk.CTkLabel(
            self._titlebar, text="AgentBK",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#A0B0DC", "#A0B0DC"),
        )
        self._title_label.pack(side="left", padx=12, pady=0)

        # Close button in title bar
        self._close_btn = ctk.CTkButton(
            self._titlebar, text="✕", width=28, height=22,
            corner_radius=6, font=ctk.CTkFont(size=12),
            fg_color="transparent", hover_color=("#8B2020", "#8B2020"),
            text_color=("#C06060", "#C06060"),
            command=self.destroy,
        )
        self._close_btn.pack(side="right", padx=6, pady=5)

        # Content area — scenes live here
        self.content = ctk.CTkFrame(self._outer, corner_radius=0, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        # Resize grip (bottom-right)
        self._grip = ctk.CTkFrame(
            self._outer, width=_GRIP_SIZE, height=_GRIP_SIZE,
            corner_radius=0, fg_color=("#2A2A4A", "#2A2A4A"),
            cursor="bottom_right_corner",
        )
        self._grip.place(relx=1.0, rely=1.0, x=-_GRIP_SIZE, y=-_GRIP_SIZE)

        # ── Bindings ────────────────────────────────────────────
        for widget in (self._titlebar, self._title_label):
            widget.bind("<Button-1>",   self._drag_start)
            widget.bind("<B1-Motion>",  self._drag_motion)
            widget.bind("<ButtonRelease-1>", self._drag_end)

        self._grip.bind("<Button-1>",   self._resize_start)
        self._grip.bind("<B1-Motion>",  self._resize_motion)
        self._grip.bind("<ButtonRelease-1>", self._resize_end)

        # Forward Configure for scene resize notifications
        self.bind("<Configure>", self._on_configure)
        self._last_wh = (_DEFAULT_W, _DEFAULT_H)
        self._scene_manager = None  # set by main_ctk after scenes are created

    # ── Drag ────────────────────────────────────────────────────────────────

    def _drag_start(self, event) -> None:
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_win_x = self.winfo_x()
        self._drag_win_y = self.winfo_y()

    def _drag_motion(self, event) -> None:
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        new_x = self._drag_win_x + dx
        new_y = self._drag_win_y + dy
        self.geometry(f"+{new_x}+{new_y}")

    def _drag_end(self, event) -> None:
        # Update anchor so next drag starts from correct position
        self._drag_win_x = self.winfo_x()
        self._drag_win_y = self.winfo_y()

    # ── Resize ──────────────────────────────────────────────────────────────

    def _resize_start(self, event) -> None:
        self._resizing = True
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.winfo_width()
        self._resize_start_h = self.winfo_height()

    def _resize_motion(self, event) -> None:
        if not self._resizing:
            return
        dw = event.x_root - self._resize_start_x
        dh = event.y_root - self._resize_start_y
        new_w = max(_MIN_W, min(_MAX_W, self._resize_start_w + dw))
        new_h = max(_MIN_H, min(_MAX_H, self._resize_start_h + dh))
        self.geometry(f"{new_w}x{new_h}")

    def _resize_end(self, event) -> None:
        self._resizing = False
        self._resize_start_w = self.winfo_width()
        self._resize_start_h = self.winfo_height()

    # ── Configure notify ────────────────────────────────────────────────────

    def _on_configure(self, event) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        if (w, h) != self._last_wh and w > 1 and h > 1:
            self._last_wh = (w, h)
            if self._scene_manager:
                self._scene_manager.notify_resize(w, h)

    # ── Always-on-top toggle ─────────────────────────────────────────────────

    def set_always_on_top(self, value: bool) -> None:
        self._always_on_top = value
        self.wm_attributes("-topmost", value)
