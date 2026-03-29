Scaffold a new UI scene.

Usage: `/new-scene <name>` (e.g. `/new-scene history`)

Steps:
1. Read `app/ui/scene_manager.py` to understand BaseScene interface
2. Read an existing scene (e.g. `app/ui/chat_scene.py`) as reference
3. Create `app/ui/<name>_scene.py` with:
   - Class `<Name>Scene(BaseScene)`
   - `__init__(self, win_w, win_h)` — store sizes only, no Rects yet
   - `_layout(self, w, h)` — compute all pygame.Rect positions dynamically
   - `handle_event(self, event)` — call `_layout` from draw only if size changed
   - `update(self)` — animation/timer logic
   - `draw(self, surface)` — call `_layout(*surface.get_size())` if size changed, then render
   - Back button using `self.manager.pop()`
4. Wire the new scene into `app/ui/main_scene.py` or wherever it should be launched from
5. Use `font_manager.get(size)` — never `pygame.font.SysFont` directly (Thai support)

Key rules:
- Dynamic layout: always check `surface.get_size()` in draw(), never hardcode window dimensions
- Decouple from agent: communicate via event queue, not direct import of AvatarRenderer in business logic
