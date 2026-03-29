# Avatar System — AgentBK-01

## Overview

Avatar เป็น **procedural bot face** วาดด้วย `pygame.draw.rect()` บน grid 16×16 units
โดยแต่ละ unit = `PIXEL = 8` screen pixels → canvas 128×128 px

ไม่ใช้ sprite sheet ภายนอก ทุก expression สร้างจาก code ล้วน

---

## Visual Design

```
col:  0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
row:
 0              [LED][LED]                     ← antenna LED (2px)
 1        [====head top highlight====]
 2        [====head body=============]
 3        [====face screen============]
 4        [    [eye L ]   [eye R ]    ]
 5        [    [pupil]    [pupil ]    ]
 6        [    [glint]    [glint ]    ]        ← droopy lid covers 4-6
 7        [                           ]
 8        [  [smile corner]  [corner] ]
 9        [      [smile arc——————]   ]
10        [                           ]
11        [====face screen bottom=====]
12        [====head bottom============]

cheek tint at cols 3,12 row 8
```

---

## Color Palette

| Constant | RGB | ใช้สำหรับ |
|----------|-----|----------|
| `_HEAD` | (42,45,78) | head body |
| `_HEAD_L` | (60,64,108) | top edge highlight |
| `_SCREEN` | (22,24,45) | face screen interior |
| `_EYE_W` | (185,205,250) | iris / eye white |
| `_EYE_P` | (55,95,215) | pupil |
| `_EYE_G` | (230,235,255) | pupil glint |
| `_LID` | (38,40,70) | eyelid (droopy) |
| `_SMILE` | (120,175,255) | smile / mouth lines |
| `_MOUTH_D` | (12,14,30) | open-mouth cavity |
| `_TEETH` | (200,220,255) | teeth row |
| `_X_COL` | (210,70,70) | X-eye (error) |
| `_ZZZ` | (130,140,195) | thinking dots |
| `_CHEEK` | (55,50,100) | cheek tint |
| `_LED_I` | (80,220,120) | idle LED (green) |
| `_LED_TH` | (255,200,50) | thinking LED (yellow) |
| `_LED_TK` | (80,200,255) | talking LED (cyan) |
| `_LED_E` | (220,60,60) | error LED (red) |
| `_LED_L` | (80+v//2, 140+v//2, 255) | loading LED (pulsing cyan) |

---

## Rendering Pipeline

```mermaid
flowchart TD
    TICK["update() — tick++"]
    BOB["bob = sin(tick×0.05)×2\n(IDLE only)"]
    BLINK["blink_t++\n>120 → close\n>126 → open, reset"]
    DROOP["THINKING → droop += 0.0015\nother → droop -= 0.06"]
    SHAKE["ERROR → shake = sin(tick×0.9)×2\nother → shake = 0"]
    LED["led_pulse = sin(tick×0.12)×0.5+0.5"]

    DRAW["draw(surface, x, y)"]
    HEAD["_draw_head()"]
    LEDDR["_draw_led()"]
    EYES["_draw_eyes()"]
    MOUTH["_draw_mouth()"]
    EXTRA["_draw_extras()"]

    TICK --> BOB --> BLINK --> DROOP --> SHAKE --> LED
    LED --> DRAW
    DRAW --> HEAD --> LEDDR --> EYES --> MOUTH --> EXTRA
```

---

## Expression per State

```mermaid
graph LR
    subgraph IDLE
        I1["eyes: open iris+pupil+glint"]
        I2["blink every ~120 ticks"]
        I3["mouth: smile corners+arc"]
        I4["LED: green solid"]
        I5["bob: sin wave ±2px"]
    end

    subgraph THINKING
        T1["eyes: droop lid slowly 0→3 rows"]
        T2["mouth: flat line"]
        T3["LED: yellow pulsing"]
        T4["dots: ... appear above-right"]
    end

    subgraph TALKING
        K1["eyes: open (no blink)"]
        K2["mouth: alternates open/smile every 5 ticks"]
        K3["LED: cyan solid"]
    end

    subgraph ERROR
        E1["eyes: X shape (red diagonals)"]
        E2["mouth: frown (flat+corners down)"]
        E3["LED: red fast blink every 6 ticks"]
        E4["head: shake sin(tick×0.9)×2"]
    end

    subgraph LOADING
        L1["eyes: open iris+pupil+glint (same as IDLE)"]
        L2["mouth: flat/neutral"]
        L3["LED: cyan pulsing (sin wave, brighter than THINKING)"]
        L4["no bob — avatar holds still"]
    end
```

---

## Eye Detail

```mermaid
graph TB
    subgraph Eye["One eye — cols cx-1 to cx+1, rows 4-6"]
        IRIS["row 4,5,6 → _EYE_W (3×3 block)"]
        PUPIL["row 5, col cx → _EYE_P"]
        GLINT["row 4, col cx+1 → _EYE_G"]
        LID["droop_rows top rows → _LID (overdraws iris)"]
    end

    subgraph Blink["blink or droop>=3"]
        SLIT["row 5, cx-1 to cx+1 → _LID (single slit)"]
    end

    subgraph ErrorEye["error eye"]
        X1["(cx-1,4) (cx+1,4) → _X_COL"]
        X2["(cx,5) → _X_COL"]
        X3["(cx-1,6) (cx+1,6) → _X_COL"]
    end
```

---

## LED Behaviour

| State | Colour | Pattern |
|-------|--------|---------|
| IDLE | `_LED_I` green | solid |
| THINKING | yellow pulse | `led_pulse` sin interpolation |
| TALKING | `_LED_TK` cyan | solid |
| ERROR | `_LED_E` red | blink every 6 ticks (on/head color) |
| LOADING | `(80+v//2, 140+v//2, 255)` cyan | pulsing (sin wave, `v` = 0-127) |

---

## Animation Timings (at 60fps)

| Animation | Period |
|-----------|--------|
| Bob wave | ~125 ticks (~2.1s full cycle) |
| Blink interval | 120 ticks (~2s), close 6 ticks |
| Droop rise (THINKING) | +0.0015/tick → full in ~667 ticks (~11s) |
| Droop fall | -0.06/tick → full reset in ~17 ticks |
| Talking mouth | toggle every 5 ticks (~12 flaps/s) |
| Error shake | sin(tick×0.9) ×2 px |
| LED pulse | sin(tick×0.12) → ~52-tick half-cycle |
| Thinking dots | (tick//25)%4 → new dot every 25 ticks |

---

## Mini Avatar (Chat Header & Menubar)

`AvatarRenderer.draw()` renders to a full 128×128 surface, then `pygame.transform.smoothscale()` scales it down:

| Context | Size | Method |
|---------|------|--------|
| Chat header | 48×48 | `smoothscale` |
| Main scene card | proportional to card | `smoothscale` |
| macOS menubar | 32×32 → displayed 16pt | Pillow → NSImage |

---

## Adding a New State

1. Add value to `AvatarState` enum in `renderer.py`
2. Handle in `update()` — droop/shake/blink logic
3. Handle in `_draw_eyes()`, `_draw_mouth()`, `_draw_led()`, `_draw_extras()`
4. Add entry to `_STATE_INFO` dict in `main_scene.py` (label + colour)
