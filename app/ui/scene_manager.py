"""Scene manager — stack-based screen switching."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class BaseScene:
    """All scenes inherit from this."""

    manager: "SceneManager"

    def on_enter(self) -> None:
        """Called when scene becomes active."""

    def on_exit(self) -> None:
        """Called when scene is removed."""

    def handle_event(self, event: "pygame.event.Event") -> None: ...

    def update(self) -> None: ...

    def draw(self, surface: "pygame.Surface") -> None: ...


class SceneManager:
    def __init__(self) -> None:
        self._stack: list[BaseScene] = []

    @property
    def current(self) -> BaseScene | None:
        return self._stack[-1] if self._stack else None

    def push(self, scene: BaseScene) -> None:
        scene.manager = self
        if self._stack:
            self._stack[-1].on_exit()
        self._stack.append(scene)
        scene.on_enter()

    def pop(self) -> None:
        if not self._stack:
            return
        self._stack.pop().on_exit()
        if self._stack:
            self._stack[-1].on_enter()

    def replace(self, scene: BaseScene) -> None:
        """Pop current and push new — no history kept."""
        scene.manager = self
        if self._stack:
            self._stack.pop().on_exit()
        self._stack.append(scene)
        scene.on_enter()

    def handle_event(self, event: "pygame.event.Event") -> None:
        if self.current:
            self.current.handle_event(event)

    def update(self) -> None:
        if self.current:
            self.current.update()

    def draw(self, surface: "pygame.Surface") -> None:
        if self.current:
            self.current.draw(surface)
