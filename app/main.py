"""Entry point — borderless, draggable, resizable, always-on-top pixel avatar bot."""

from __future__ import annotations

import sys
import pygame
from dotenv import load_dotenv

from app.ui.scene_manager  import SceneManager
from app.ui.main_scene     import MainScene
from app.tray              import menubar
from app.agent.router      import AgentRouter

load_dotenv()

from app import dev_log  # noqa: E402
dev_log.banner()

WIN_W  = 360
WIN_H  = 520
MIN_W  = 160   # เล็กสุด — แค่ avatar + badge
MIN_H  = 190
MAX_W  = 700
MAX_H  = 900
FPS    = 60
TITLE  = "AgentBK"

GRIP_SIZE  = 18   # resize handle bottom-right corner (px)
DRAG_ZONE_H = 54  # header drag area height

GRIP_COL   = ( 70,  80, 120)
GRIP_HOV   = (110, 130, 180)


def main() -> None:
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass   # audio unavailable — TTS falls back to macOS say
    pygame.display.set_caption(TITLE)

    # RESIZABLE ให้ set_mode ใหม่ได้, NOFRAME = borderless
    screen = pygame.display.set_mode(
        (WIN_W, WIN_H),
        pygame.NOFRAME | pygame.RESIZABLE,
    )

    sdl_win = _get_sdl_win()
    if sdl_win:
        sdl_win.always_on_top = True
        # Center window on primary screen (avoid off-screen from external monitor)
        try:
            from AppKit import NSScreen
            main_screen = NSScreen.mainScreen()
            screen_frame = main_screen.frame()
            sw = int(screen_frame.size.width)
            sh = int(screen_frame.size.height)
            x = (sw - WIN_W) // 2
            y = (sh - WIN_H) // 2
            sdl_win.position = (x, y)
        except Exception:
            # Fallback: safe visible position
            sdl_win.position = (100, 100)

    # ── macOS menu bar icon ──────────────────────────────────────────────────
    # setup หลัง pygame.init() เพื่อให้ NSApplication พร้อมแล้ว
    toggle_window = menubar.make_toggle(sdl_win)
    menubar.setup(
        on_toggle=toggle_window,
        on_quit=lambda: None,   # QUIT event handled in loop
    )

    clock  = pygame.time.Clock()
    router = AgentRouter()
    scenes = SceneManager()
    scenes.push(MainScene(WIN_W, WIN_H, router))

    cur_w, cur_h = WIN_W, WIN_H

    # ── drag-to-move state ───────────────────────────────────────────────────
    # Anchor approach: เก็บ offset ของ mouse ภายใน window ณ ตอน click
    # ทุก MOUSEMOTION → new_win_pos = global_mouse - anchor
    # ไม่ใช้ event.rel สะสม → ไม่มี drift เมื่อ window เคลื่อนที่
    is_dragging        = False
    drag_anchor        = (0, 0)   # mouse offset ภายใน window ณ ตอน mousedown
    tracked_win_pos    = (0, 0)   # position ที่เราเขียนเองล่าสุด (ไม่ read-back)

    # ── resize state ─────────────────────────────────────────────────────────
    is_resizing          = False
    resize_win_orig      = (WIN_W, WIN_H)
    resize_cum_dx        = 0
    resize_cum_dy        = 0
    grip_hovered         = False

    def grip_rect() -> pygame.Rect:
        return pygame.Rect(cur_w - GRIP_SIZE, cur_h - GRIP_SIZE, GRIP_SIZE, GRIP_SIZE)

    def apply_size(new_w: int, new_h: int) -> None:
        nonlocal screen, cur_w, cur_h
        new_w = max(MIN_W, min(MAX_W, new_w))
        new_h = max(MIN_H, min(MAX_H, new_h))
        if new_w == cur_w and new_h == cur_h:
            return
        cur_w, cur_h = new_w, new_h
        screen = pygame.display.set_mode(
            (cur_w, cur_h), pygame.NOFRAME | pygame.RESIZABLE
        )

    # sync tracked_win_pos กับ initial window position
    if sdl_win:
        try:
            tracked_win_pos = tuple(sdl_win.position)
        except Exception:
            tracked_win_pos = (0, 0)

    running = True
    while running:
        clock.tick_busy_loop(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ── hover grip ───────────────────────────────────────────────────
            if event.type == pygame.MOUSEMOTION:
                grip_hovered = grip_rect().collidepoint(event.pos)

            # ── mouse down ───────────────────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if grip_rect().collidepoint(event.pos):
                    is_resizing     = True
                    resize_win_orig = (cur_w, cur_h)
                    resize_cum_dx   = 0
                    resize_cum_dy   = 0
                elif event.pos[1] <= DRAG_ZONE_H:
                    is_dragging  = True
                    # anchor = mouse position ภายใน window — คงที่ตลอด drag
                    drag_anchor  = event.pos

            # ── mouse up ─────────────────────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                is_resizing = False
                is_dragging = False

            # ── resize drag ──────────────────────────────────────────────────
            if event.type == pygame.MOUSEMOTION and is_resizing:
                resize_cum_dx += event.rel[0]
                resize_cum_dy += event.rel[1]
                apply_size(resize_win_orig[0] + resize_cum_dx,
                           resize_win_orig[1] + resize_cum_dy)
                continue

            # ── window move drag (anchor: new_pos = global_mouse - anchor) ──
            if event.type == pygame.MOUSEMOTION and is_dragging:
                if sdl_win:
                    # global mouse = tracked window pos + event.pos (window-relative)
                    gx = tracked_win_pos[0] + event.pos[0]
                    gy = tracked_win_pos[1] + event.pos[1]
                    new_x = gx - drag_anchor[0]
                    new_y = gy - drag_anchor[1]
                    sdl_win.position = (new_x, new_y)
                    tracked_win_pos = (new_x, new_y)
                continue

            scenes.handle_event(event)

        scenes.update()

        # ── draw ─────────────────────────────────────────────────────────────
        try:
            scenes.draw(screen)
        except Exception as _draw_exc:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
        _draw_grip(screen, grip_rect(), grip_hovered)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


def _draw_grip(surface: pygame.Surface, rect: pygame.Rect, hovered: bool) -> None:
    """Draw resize grip — 3 diagonal dotted lines at bottom-right."""
    col = GRIP_HOV if hovered else GRIP_COL
    d = 4  # dot spacing
    for i in range(3):
        offset = i * d + d
        x1 = rect.right - offset
        y1 = rect.bottom - d
        x2 = rect.right - d
        y2 = rect.bottom - offset
        if x1 >= rect.left and y2 >= rect.top:
            pygame.draw.line(surface, col, (x1, y1), (x2, y2), 2)


def _get_sdl_win():
    try:
        import warnings
        from pygame._sdl2.video import Window as SDLWindow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return SDLWindow.from_display_module()
    except Exception:
        return None


if __name__ == "__main__":
    main()
