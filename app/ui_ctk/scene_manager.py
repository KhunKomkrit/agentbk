"""Scene manager — stack-based frame switching for CustomTkinter."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import customtkinter as ctk


class BaseScene:
    """All scenes inherit from this.

    Lifecycle:
        on_enter()  — called when scene becomes the active top of stack
        on_exit()   — called when scene is popped or replaced
        on_resize(w, h) — called by AppWindow <Configure> events

    Every scene must call ``self._build(parent)`` in its ``__init__`` to
    create its CTkFrame.  The SceneManager owns show/hide.
    """

    manager: "SceneManager"
    frame: "ctk.CTkFrame"

    def on_enter(self) -> None:
        """Called when scene becomes active."""

    def on_exit(self) -> None:
        """Called when scene is removed from top."""

    def on_resize(self, w: int, h: int) -> None:
        """Called when the root window is resized."""


class SceneManager:
    def __init__(self, container: "ctk.CTkFrame") -> None:
        """
        Args:
            container: A full-size CTkFrame that the scenes are packed into.
        """
        self._container = container
        self._stack: list[BaseScene] = []

    @property
    def current(self) -> BaseScene | None:
        return self._stack[-1] if self._stack else None

    def _show(self, scene: BaseScene) -> None:
        scene.frame.pack(fill="both", expand=True)

    def _hide(self, scene: BaseScene) -> None:
        scene.frame.pack_forget()

    def push(self, scene: BaseScene) -> None:
        scene.manager = self
        if self._stack:
            top = self._stack[-1]
            top.on_exit()
            self._hide(top)
        self._stack.append(scene)
        scene.frame.master = self._container  # type: ignore[assignment]
        self._show(scene)
        scene.on_enter()

    def pop(self) -> None:
        if not self._stack:
            return
        top = self._stack.pop()
        top.on_exit()
        self._hide(top)
        if self._stack:
            prev = self._stack[-1]
            self._show(prev)
            prev.on_enter()

    def replace(self, scene: BaseScene) -> None:
        """Pop current (no history) and push new scene."""
        scene.manager = self
        if self._stack:
            top = self._stack.pop()
            top.on_exit()
            self._hide(top)
        self._stack.append(scene)
        self._show(scene)
        scene.on_enter()

    def notify_resize(self, w: int, h: int) -> None:
        if self.current:
            self.current.on_resize(w, h)
