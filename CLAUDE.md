# agentbk-01 — Pixel Avatar AI Bot

## Vision

Desktop bot (macOS/PC) ที่มี pixel art avatar เป็นหน้าตา — borderless, always-on-top, ลากย้ายได้
เบื้องหลัง route ไปยัง LLM หลายเจ้า (Anthropic, OpenAI, Ollama) ผ่าน provider adapter pattern

---

## Quick Start

```bash
uv sync
cp .env.example .env   # ใส่ API keys
uv run python -m app.main
```

---

## Actual File Structure (as-built)

```
agentbk-01/
├── CLAUDE.md
├── pyproject.toml          uv + hatchling
├── .env.example
├── uv.lock
│
├── .claude/
│   ├── settings.json       permissions + post-edit ruff hook
│   └── commands/           slash commands
│       ├── run.md           /run  — launch app
│       ├── check.md         /check — ruff + mypy
│       ├── test.md          /test [--all]
│       ├── new-provider.md  /new-provider <name>
│       ├── new-scene.md     /new-scene <name>
│       └── avatar.md        /avatar [state]
│
├── app/
│   ├── main.py              entry point: window, drag, resize, scene loop
│   │
│   ├── avatar/
│   │   └── renderer.py      AvatarRenderer, AvatarState, procedural pixel draw
│   │
│   ├── ui/
│   │   ├── font_manager.py  Thai font loader (SukhumvitSet → Ayuthaya → fallback)
│   │   ├── button.py        pixel-style Button widget
│   │   ├── scene_manager.py SceneManager (push/pop/replace stack)
│   │   ├── main_scene.py    avatar + [Chat][Voice][Settings] buttons
│   │   ├── chat_scene.py    chat history + input + mini avatar header
│   │   └── settings_scene.py provider/model/display settings
│   │
│   ├── agent/               (Phase 2 — not yet built)
│   │   ├── router.py
│   │   ├── memory.py
│   │   └── tools.py
│   │
│   └── providers/           (Phase 2 — not yet built)
│       ├── base.py
│       ├── anthropic_provider.py
│       ├── openai_provider.py
│       └── ollama_provider.py
│
├── docs/
│   ├── 00-index.md
│   ├── 01-architecture.md
│   ├── 02-ui-design.md
│   ├── 03-avatar-system.md
│   ├── 04-llm-providers.md
│   └── 05-dev-guide.md
│
└── tests/
```

---

## Architecture

```
main.py
  └── SceneManager
        ├── MainScene      → ChatScene (push)
        │                  → SettingsScene (push)
        ├── ChatScene      → MainScene (pop)
        └── SettingsScene  → MainScene (pop)

AvatarRenderer (shared instance, passed between scenes)
  └── AvatarState: IDLE | THINKING | TALKING | ERROR
```

Window management (all in `main.py`):
- `pygame.NOFRAME | pygame.RESIZABLE` — borderless, resizable
- `sdl_win.always_on_top = True` — float above other windows
- Drag: `drag_win_orig + cumulative event.rel` — smooth, no async drift
- Resize: bottom-right grip, same cumulative pattern
- Min: 160×190 / Max: 700×900

---

## UI Scene Pattern

ทุก scene ต้อง:
1. **ไม่ hardcode ขนาดหน้าต่าง** — อ่าน `surface.get_size()` ใน `draw()`
2. มี `_layout(w, h)` สำหรับคำนวณ Rect ทุกตัว
3. เรียก `_layout` เฉพาะเมื่อขนาดเปลี่ยน (`self._last_size != (w, h)`)
4. ใช้ `font_manager.get(size)` เสมอ — ห้าม `pygame.font.SysFont` โดยตรง (Thai ไม่ออก)

```python
def draw(self, surface: pygame.Surface) -> None:
    w, h = surface.get_size()
    if (w, h) != self._last_size:
        self._layout(w, h)
    # ... render
```

---

## Provider Interface (Phase 2)

```python
class BaseLLMProvider:
    name: str
    model: str
    async def chat(self, messages: list[dict], **kwargs) -> str: ...
    async def stream(self, messages, **kwargs) -> AsyncIterator[str]: ...
```

- Router เลือก provider จาก `ACTIVE_PROVIDER` env var
- `async/await` ทุก layer ของ agent/provider
- Avatar state ส่งผ่าน event queue — ไม่ import AvatarRenderer ใน agent

---

## Coding Conventions

| Rule | Why |
|------|-----|
| Type hints บน public functions ทุกตัว | mypy + IDE support |
| `async/await` ใน agent + provider layer | ไม่บล็อก pygame event loop |
| One provider per file ใน `providers/` | isolate ง่าย, test แยกได้ |
| Dynamic layout ใน scenes | รองรับ resize ได้ทุกขนาด |
| `font_manager.get()` เสมอ | Thai font ออก |
| Avatar ↔ Agent ผ่าน event queue เท่านั้น | ไม่ tight-couple |

---

## Environment Variables

```
ACTIVE_PROVIDER=anthropic        # anthropic | openai | ollama
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

---

## Slash Commands (`.claude/commands/`)

| Command | ทำอะไร |
|---------|--------|
| `/run` | ตรวจ env → uv sync → launch app |
| `/check` | ruff lint/format + mypy |
| `/test [--all]` | pytest unit / integration |
| `/new-provider <name>` | scaffold LLM adapter ใหม่ |
| `/new-scene <name>` | scaffold UI scene ใหม่ |
| `/avatar [state]` | อธิบาย / ทดสอบ avatar state |

---

## Current Status

| Phase | Status |
|-------|--------|
| Phase 1 — UI (avatar, scenes, drag, resize, Thai font) | ✅ Done |
| Phase 2 — LLM providers + agent router | 🔜 Next |
| Phase 3 — Conversation memory + tools | ⬜ Planned |
| Phase 4 — Sprite assets + TTS voice | ⬜ Planned |
