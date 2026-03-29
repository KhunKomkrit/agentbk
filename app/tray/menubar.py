"""macOS menu bar integration — NSStatusItem with pixel avatar icon."""

from __future__ import annotations

import io
from typing import Callable

import pygame

_status_item = None   # keep reference alive (prevent GC)
_handler     = None


def setup(on_toggle: Callable, on_quit: Callable) -> None:
    """
    Call AFTER pygame.init() — SDL2 already started NSApplication by then.
    Injects an NSStatusItem into the macOS system menu bar.
    """
    try:
        import objc
        from Foundation import NSObject
        from AppKit import (
            NSStatusBar, NSVariableStatusItemLength,
            NSMenu, NSMenuItem,
        )
    except ImportError:
        return  # not macOS or pyobjc not installed

    global _status_item, _handler

    # ── Action handler — use closures, not ObjC-style init args ─────────────
    # Defining class inside setup() lets IBAction methods close over
    # on_toggle / on_quit without going through ObjC method arguments.
    class _Handler(NSObject):   # type: ignore[misc]

        @objc.IBAction  # type: ignore[misc]
        def toggleWindow_(self, sender: object) -> None:
            on_toggle()

        @objc.IBAction  # type: ignore[misc]
        def quitApp_(self, sender: object) -> None:
            on_quit()
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    _handler = _Handler.alloc().init()

    # ── Create NSStatusItem ───────────────────────────────────────────────────
    _status_item = (
        NSStatusBar.systemStatusBar()
        .statusItemWithLength_(NSVariableStatusItemLength)
    )

    ns_image = _make_menubar_icon()
    if ns_image:
        _status_item.button().setImage_(ns_image)
    else:
        _status_item.button().setTitle_("👾")

    # ── Menu ──────────────────────────────────────────────────────────────────
    menu = NSMenu.alloc().init()
    menu.setAutoenablesItems_(False)

    def _make_item(title: str, action: str, key: str = "") -> NSMenuItem:
        # action ต้องเป็น ObjC selector format: "methodName:" (ใช้ : ไม่ใช่ _)
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, action, key
        )
        it.setTarget_(_handler)
        it.setEnabled_(True)
        return it

    menu.addItem_(_make_item("แสดง / ซ่อน AgentBK", "toggleWindow:"))
    menu.addItem_(NSMenuItem.separatorItem())
    menu.addItem_(_make_item("ออกจากโปรแกรม", "quitApp:", "q"))

    _status_item.setMenu_(menu)


# ── Icon builder ──────────────────────────────────────────────────────────────

def _make_menubar_icon() -> object | None:
    """Render the bot avatar face → NSImage for the macOS menu bar."""
    try:
        from AppKit import NSImage
        from Foundation import NSData
        from PIL import Image as PILImage
        from app.avatar.renderer import AvatarRenderer, AvatarState

        SIZE = 32   # 32×32 looks sharp on retina (macOS scales to 16pt)

        av = AvatarRenderer()
        av.state = AvatarState.IDLE

        # Render to a full-size pygame surface, then scale down
        full = pygame.Surface((av.width, av.height), pygame.SRCALPHA)
        full.fill((0, 0, 0, 0))
        av.draw(full, 0, 0)
        scaled = pygame.transform.smoothscale(full, (SIZE, SIZE))

        # pygame Surface → raw RGBA bytes → PIL Image
        raw = pygame.image.tobytes(scaled, "RGBA")
        pil = PILImage.frombytes("RGBA", (SIZE, SIZE), raw)

        buf      = io.BytesIO()
        pil.save(buf, format="PNG")
        data     = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
        ns_image = NSImage.alloc().initWithData_(data)
        ns_image.setSize_((16, 16))   # display size in pts (will be crisp on retina)
        # Do NOT setTemplate_ — bot face is coloured
        return ns_image

    except Exception:
        return None


# ── Window toggle helper ──────────────────────────────────────────────────────

def make_toggle(sdl_win: object) -> Callable:
    """Returns a callback that shows/hides the pygame window."""
    _visible = [True]

    def toggle() -> None:
        if sdl_win is None:
            return
        if _visible[0]:
            try:
                sdl_win.hide()   # type: ignore[union-attr]
            except Exception:
                pass
        else:
            try:
                sdl_win.show()   # type: ignore[union-attr]
                sdl_win.focus()  # type: ignore[union-attr]
            except Exception:
                pass
        _visible[0] = not _visible[0]

    return toggle
