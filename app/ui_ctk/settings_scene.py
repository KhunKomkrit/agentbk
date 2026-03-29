"""SettingsScene — provider, model, always-on-top, MCP server management."""
from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.ui_ctk.scene_manager import BaseScene
from app.ui_ctk import font_manager
from app.agent.mcp_config import load_servers, save_servers, MCP_PRESETS

if TYPE_CHECKING:
    from app.agent.router import AgentRouter

_PROVIDERS = ["anthropic", "openai", "ollama"]
_PROVIDER_LABELS = {
    "anthropic": "Anthropic Claude",
    "openai":    "OpenAI GPT",
    "ollama":    "Ollama (Local)",
}
_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "ollama":    ["qwen2.5:3b", "qwen2.5-coder:7b", "llama3.2:3b", "mistral", "phi3.5"],
}


class SettingsScene(BaseScene):
    def __init__(self, parent: ctk.CTkFrame, router: "AgentRouter | None" = None) -> None:
        self._router = router
        self._provider = os.getenv("ACTIVE_PROVIDER", "anthropic")
        self._model_idx = 0
        self._always_on_top = True
        self._mcp_servers: list[dict] = load_servers()

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

        ctk.CTkLabel(
            header, text="Settings",
            font=font_manager.ctk_font(13, bold=True),
            text_color=("#A0B0DC", "#A0B0DC"),
        ).pack(side="left", expand=True)

        # ── Scrollable body ───────────────────────────────────────────────
        body = ctk.CTkScrollableFrame(
            self.frame, corner_radius=0,
            fg_color=("#1A1A30", "#1A1A30"),
            scrollbar_button_color=("#303050", "#303050"),
            scrollbar_button_hover_color=("#404070", "#404070"),
        )
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        # ── Section: Provider ─────────────────────────────────────────────
        self._section(body, "LLM Provider")

        prov_labels = [_PROVIDER_LABELS[p] for p in _PROVIDERS]
        cur_label = _PROVIDER_LABELS.get(self._provider, prov_labels[0])
        self._prov_menu = ctk.CTkOptionMenu(
            body, values=prov_labels,
            font=font_manager.ctk_font(13),
            fg_color=("#2A2A4A", "#2A2A4A"),
            button_color=("#3A3A6A", "#3A3A6A"),
            button_hover_color=("#5050A0", "#5050A0"),
            command=self._on_provider_change,
        )
        self._prov_menu.set(cur_label)
        self._prov_menu.pack(fill="x", padx=14, pady=(0, 8))

        # ── Section: Model ────────────────────────────────────────────────
        self._section(body, "Model")

        model_row = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        model_row.pack(fill="x", padx=14, pady=(0, 8))
        model_row.columnconfigure(0, weight=1)

        self._model_menu = ctk.CTkOptionMenu(
            model_row, values=self._current_models(),
            font=font_manager.ctk_font(13),
            fg_color=("#2A2A4A", "#2A2A4A"),
            button_color=("#3A3A6A", "#3A3A6A"),
            button_hover_color=("#5050A0", "#5050A0"),
            command=self._on_model_change,
        )
        current_models = self._current_models()
        self._model_menu.set(current_models[0] if current_models else "")
        self._model_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._refresh_btn = ctk.CTkButton(
            model_row, text="↻", width=34, height=32, corner_radius=6,
            font=font_manager.ctk_font(14),
            fg_color=("#2A3A6A", "#2A3A6A"),
            hover_color=("#3A5090", "#3A5090"),
            command=self._refresh_ollama,
        )
        self._refresh_btn.grid(row=0, column=1, sticky="e")
        self._refresh_btn.grid_remove()  # only shown for Ollama
        self._update_refresh_btn_visibility()

        # ── Section: Display ──────────────────────────────────────────────
        self._section(body, "Display")

        aot_row = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        aot_row.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(
            aot_row, text="Always on Top",
            font=font_manager.ctk_font(13),
            text_color=("#A0B0DC", "#A0B0DC"),
        ).pack(side="left")

        self._aot_switch = ctk.CTkSwitch(
            aot_row, text="",
            onvalue=True, offvalue=False,
            command=self._on_aot_toggle,
            fg_color=("#2A2A4A", "#2A2A4A"),
            progress_color=("#3C8C3C", "#3C8C3C"),
        )
        self._aot_switch.pack(side="right")
        if self._always_on_top:
            self._aot_switch.select()

        # ── Section: Conversation ─────────────────────────────────────────
        self._section(body, "Conversation")

        ctk.CTkButton(
            body, text="🗑  Clear History",
            font=font_manager.ctk_font(13),
            height=32, corner_radius=6,
            fg_color=("#5A2020", "#5A2020"),
            hover_color=("#802828", "#802828"),
            command=self._clear_history,
        ).pack(fill="x", padx=14, pady=(0, 12))

        # ── Section: MCP Servers ──────────────────────────────────────────
        self._section(body, "MCP Servers")
        self._mcp_body = body
        self._mcp_rows_frame = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        self._mcp_rows_frame.pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkButton(
            body, text="+ Add Server",
            font=font_manager.ctk_font(12),
            height=28, corner_radius=6,
            fg_color=("#1E4A2E", "#1E4A2E"),
            hover_color=("#2A6A40", "#2A6A40"),
            command=self._add_server_dialog,
        ).pack(fill="x", padx=14, pady=(0, 12))

        self._rebuild_mcp_rows()

        # Status label
        self._status_label = ctk.CTkLabel(
            self.frame, text="",
            font=font_manager.ctk_font(11),
            text_color=("#5090D0", "#5090D0"),
            height=20,
        )
        self._status_label.pack(fill="x", padx=12, pady=(2, 4))

    # ── Section helper ─────────────────────────────────────────────────────────

    def _section(self, parent, title: str) -> None:
        ctk.CTkLabel(
            parent, text=title,
            font=font_manager.ctk_font(11, bold=True),
            text_color=("#6070A0", "#6070A0"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))

    # ── Provider / Model ───────────────────────────────────────────────────────

    def _current_models(self) -> list[str]:
        return _MODELS.get(self._provider, ["default"])

    def _on_provider_change(self, label: str) -> None:
        for key, val in _PROVIDER_LABELS.items():
            if val == label:
                self._provider = key
                break
        os.environ["ACTIVE_PROVIDER"] = self._provider
        models = self._current_models()
        self._model_menu.configure(values=models)
        self._model_menu.set(models[0] if models else "")
        self._update_refresh_btn_visibility()
        self._show_status("Provider updated — restart to apply")

    def _on_model_change(self, model: str) -> None:
        os.environ["ACTIVE_MODEL"] = model
        self._show_status(f"Model: {model}")

    def _update_refresh_btn_visibility(self) -> None:
        if self._provider == "ollama":
            self._refresh_btn.grid()
        else:
            self._refresh_btn.grid_remove()

    def _refresh_ollama(self) -> None:
        self._show_status("Refreshing Ollama models…")

        def _work() -> None:
            try:
                import httpx
                resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
                resp.raise_for_status()
                names = [m["name"] for m in resp.json().get("models", [])]
                if names:
                    existing = list(_MODELS.get("ollama", []))
                    for n in names:
                        if n not in existing:
                            existing.append(n)
                    _MODELS["ollama"] = existing
                self.frame.after(0, lambda: self._on_ollama_refreshed(names))
            except Exception as e:
                self.frame.after(0, lambda: self._show_status(f"⚠ {e}"))

        threading.Thread(target=_work, daemon=True).start()

    def _on_ollama_refreshed(self, names: list[str]) -> None:
        models = self._current_models()
        self._model_menu.configure(values=models)
        if models:
            self._model_menu.set(models[0])
        self._show_status(f"Found {len(names)} Ollama models")

    # ── Display ────────────────────────────────────────────────────────────────

    def _on_aot_toggle(self) -> None:
        value = bool(self._aot_switch.get())
        self._always_on_top = value
        # Walk up to the root window and toggle
        root = self.frame.winfo_toplevel()
        root.wm_attributes("-topmost", value)

    # ── Conversation ────────────────────────────────────────────────────────────

    def _clear_history(self) -> None:
        if self._router:
            self._router.clear_history()  # type: ignore[attr-defined]
        self._show_status("History cleared")

    # ── MCP servers ────────────────────────────────────────────────────────────

    def _rebuild_mcp_rows(self) -> None:
        for child in self._mcp_rows_frame.winfo_children():
            child.destroy()

        for idx, srv in enumerate(self._mcp_servers):
            self._build_mcp_row(idx, srv)

    def _build_mcp_row(self, idx: int, srv: dict) -> None:
        row = ctk.CTkFrame(
            self._mcp_rows_frame, corner_radius=6,
            fg_color=("#1E1E38", "#1E1E38"),
        )
        row.pack(fill="x", pady=2)
        row.columnconfigure(0, weight=1)

        enabled_var = ctk.BooleanVar(value=srv.get("enabled", True))
        ctk.CTkCheckBox(
            row, text=srv.get("name", srv.get("url", "")),
            variable=enabled_var,
            font=font_manager.ctk_font(12),
            text_color=("#A0B0DC", "#A0B0DC"),
            fg_color=("#3A5090", "#3A5090"),
            hover_color=("#5070C0", "#5070C0"),
            command=lambda i=idx, v=enabled_var: self._toggle_mcp(i, v.get()),
        ).pack(side="left", padx=8, pady=6, fill="x", expand=True)

        ctk.CTkButton(
            row, text="✕", width=24, height=22, corner_radius=4,
            font=font_manager.ctk_font(11),
            fg_color="transparent",
            hover_color=("#602020", "#602020"),
            text_color=("#C06060", "#C06060"),
            command=lambda i=idx: self._delete_mcp(i),
        ).pack(side="right", padx=4, pady=4)

        ctk.CTkButton(
            row, text="✎", width=24, height=22, corner_radius=4,
            font=font_manager.ctk_font(11),
            fg_color="transparent",
            hover_color=("#204060", "#204060"),
            text_color=("#6090C0", "#6090C0"),
            command=lambda i=idx: self._edit_mcp_dialog(i),
        ).pack(side="right", padx=0, pady=4)

    def _toggle_mcp(self, idx: int, enabled: bool) -> None:
        if 0 <= idx < len(self._mcp_servers):
            self._mcp_servers[idx]["enabled"] = enabled
            save_servers(self._mcp_servers)

    def _delete_mcp(self, idx: int) -> None:
        if 0 <= idx < len(self._mcp_servers):
            self._mcp_servers.pop(idx)
            save_servers(self._mcp_servers)
            self._rebuild_mcp_rows()
            self._show_status("Server removed")

    def _add_server_dialog(self) -> None:
        self._mcp_form_dialog(edit_idx=None)

    def _edit_mcp_dialog(self, idx: int) -> None:
        self._mcp_form_dialog(edit_idx=idx)

    def _mcp_form_dialog(self, edit_idx: int | None) -> None:
        """Open a CTkToplevel form for add/edit MCP server."""
        dlg = ctk.CTkToplevel(self.frame)
        dlg.title("MCP Server" if edit_idx is None else "Edit Server")
        dlg.geometry("340x340")
        dlg.grab_set()

        existing = self._mcp_servers[edit_idx] if edit_idx is not None else {}

        ctk.CTkLabel(dlg, text="Name", font=font_manager.ctk_font(12)).pack(anchor="w", padx=16, pady=(16, 2))
        name_entry = ctk.CTkEntry(dlg, font=font_manager.ctk_font(13), placeholder_text="My MCP Server")
        name_entry.pack(fill="x", padx=16, pady=(0, 8))
        if existing.get("name"):
            name_entry.insert(0, existing["name"])

        ctk.CTkLabel(dlg, text="URL", font=font_manager.ctk_font(12)).pack(anchor="w", padx=16, pady=(0, 2))
        url_entry = ctk.CTkEntry(dlg, font=font_manager.ctk_font(13), placeholder_text="http://localhost:8000/mcp")
        url_entry.pack(fill="x", padx=16, pady=(0, 8))
        if existing.get("url"):
            url_entry.insert(0, existing["url"])

        # Presets
        ctk.CTkLabel(dlg, text="Presets", font=font_manager.ctk_font(11),
                     text_color=("#6070A0", "#6070A0")).pack(anchor="w", padx=16, pady=(0, 4))
        for preset in MCP_PRESETS:
            def _fill(p=preset):
                url_entry.delete(0, "end")
                url_entry.insert(0, p["url"])
                if not name_entry.get():
                    name_entry.insert(0, p["label"])
            ctk.CTkButton(
                dlg, text=preset["label"],
                font=font_manager.ctk_font(11),
                height=24, corner_radius=4,
                fg_color=("#2A3060", "#2A3060"),
                hover_color=("#3A4090", "#3A4090"),
                command=_fill,
            ).pack(fill="x", padx=16, pady=2)

        def _save() -> None:
            name = name_entry.get().strip()
            url = url_entry.get().strip()
            if not url:
                return
            entry = {"name": name or url, "url": url, "enabled": True}
            if edit_idx is None:
                self._mcp_servers.append(entry)
            else:
                self._mcp_servers[edit_idx] = entry
            save_servers(self._mcp_servers)
            self._rebuild_mcp_rows()
            dlg.destroy()
            self._show_status("Server saved")

        ctk.CTkButton(
            dlg, text="Save",
            font=font_manager.ctk_font(13),
            height=32, corner_radius=6,
            fg_color=("#1E5A34", "#1E5A34"),
            hover_color=("#2A8048", "#2A8048"),
            command=_save,
        ).pack(fill="x", padx=16, pady=12)

    # ── Nav + Status ─────────────────────────────────────────────────────────────

    def _go_back(self) -> None:
        self.manager.pop()

    def _show_status(self, msg: str, ms: int = 2500) -> None:
        self._status_label.configure(text=msg)
        self.frame.after(ms, lambda: self._status_label.configure(text=""))
