"""main_ctk.py — CustomTkinter entry point for agentbk-01."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    # Import CTk first so Tk is available before any scene imports
    import customtkinter as ctk

    from app.ui_ctk.app_window import AppWindow
    from app.ui_ctk.scene_manager import SceneManager
    from app.ui_ctk.main_scene import MainScene
    from app.agent.router import AgentRouter

    # Initialise the router in a background thread (AgentRouter does it internally)
    router = AgentRouter()

    # Build window
    win = AppWindow(always_on_top=True)

    # Scene manager wired to the content area
    sm = SceneManager(win.content)
    win._scene_manager = sm

    # Push main scene
    main_scene = MainScene(win.content, router=router)
    sm.push(main_scene)

    # Start macOS menu-bar (tray icon) if available
    try:
        from app.tray.menubar import MenuBarIcon
        MenuBarIcon(app=win).start()
    except Exception:
        pass   # tray is optional

    win.mainloop()


if __name__ == "__main__":
    main()
