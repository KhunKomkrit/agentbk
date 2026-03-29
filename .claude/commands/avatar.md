Inspect or change the avatar state for testing.

Usage: `/avatar [idle|thinking|talking|error]`

Steps:
1. Read `app/avatar/renderer.py` to understand AvatarState enum and rendering logic
2. If an argument is given, show a code snippet to set the state:
   ```python
   avatar.state = AvatarState.<STATE>
   ```
3. Explain what visual changes happen for that state:
   - idle: bob animation, blink every ~120 ticks
   - thinking: 3 dots cycling above head
   - talking: mouth open/close every 6 ticks
   - error: red tint 35%, sad mouth (MOUTH_THINK)
4. If user wants to add a new state: read renderer.py fully, then add to AvatarState enum,
   `_STATE_INFO` dict in main_scene.py, and the draw logic in `_draw_avatar_scaled`.
