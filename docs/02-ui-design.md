# UI Design — AgentBK-01

## Window Layout

```mermaid
block-beta
    columns 1
    block:window["🖥️ Window 520 × 680 px"]:1
        block:avatar_panel["Avatar Panel (h: 180px)\nBG: #19192A"]:1
            AV["👾 Pixel Avatar\n128×128px (centered)"]
            ST["● state label"]
        end
        block:chat_panel["Chat Panel (h: 488px)\nBG: #1C1C2D"]:1
            HIST["Message History\n(scrollable)"]
            INPUT["[ Text Input Box ]\n(h: 44px, bottom)"]
        end
    end
```

---

## Color System

```mermaid
graph LR
    subgraph Background
        BG["#12121E\nMain BG"]
        PANEL["#1C1C2D\nPanel BG"]
        AVATAR_BG["#19192A\nAvatar Panel"]
    end

    subgraph Bubbles
        USER_B["#3C5AA0\nUser Bubble"]
        BOT_B["#282D46\nBot Bubble"]
    end

    subgraph Text
        TEXT["#DCDCF0\nMain Text"]
        HINT["#646482\nHint / Placeholder"]
    end

    subgraph Input
        INP_BG["#232337\nInput BG"]
        INP_FOCUS["#5082C8\nFocus Border"]
    end

    subgraph States
        IDLE_C["#50A050\n● idle"]
        THINK_C["#B4B450\n● thinking"]
        TALK_C["#5082C8\n● talking"]
        ERR_C["#C85050\n● error"]
    end
```

---

## UI States

```mermaid
stateDiagram-v2
    direction LR

    state "Idle" as S1 {
        note: Avatar bob ขึ้นลง\nกะพริบตา\nInput ใช้ได้
    }
    state "Thinking" as S2 {
        note: 3 จุดวิ่งเหนือหัว\nInput disabled\nChat แสดง "..."
    }
    state "Talking" as S3 {
        note: ปากเปิด-ปิด\nToken stream ไหลเข้า chat\nInput disabled
    }
    state "Error" as S4 {
        note: Avatar สีแดง\nแสดง error message\nInput ใช้ได้อีกครั้ง
    }

    [*] --> S1
    S1 --> S2 : ส่งข้อความ
    S2 --> S3 : ได้รับ token แรก
    S3 --> S1 : LLM จบ
    S2 --> S4 : API error
    S3 --> S4 : Stream error
    S4 --> S1 : ส่งข้อความใหม่
```

---

## Chat Bubble Layout

```mermaid
graph TB
    subgraph Chat["Chat History Area"]
        B1["      [ BOT ] สวัสดี! ฉันคือ AgentBK"]
        B2["[ USER ] สวัสดีครับ      "]
        B3["      [ BOT ] ยินดีที่ได้รู้จัก!"]
        B4["[ USER ] คุณทำอะไรได้บ้าง?"]
    end

    note1["BOT bubble: ชิดซ้าย\nสี #282D46\nRadius 10px"]
    note2["USER bubble: ชิดขวา\nสี #3C5AA0\nRadius 10px"]
```

---

## Input Box Behavior

```mermaid
flowchart LR
    A([User Focus]) --> B[แสดง border สีฟ้า\n#5082C8]
    B --> C{มีข้อความ?}
    C -->|ไม่มี| D[แสดง placeholder\nสีเทา hint]
    C -->|มี| E[แสดงข้อความ + cursor |]
    E --> F{กด Enter?}
    F -->|ใช่, ไม่ว่าง| G[emit SUBMIT_EVENT\nclear input]
    F -->|Backspace| H[ลบตัวอักษรสุดท้าย]
    F -->|ตัวอักษร| I[append to buffer]
```

---

## Responsive Scaling (macOS Retina)

```mermaid
graph LR
    APP["App ขนาด\n520×680 (logical)"]
    FLAG["pygame.SCALED flag"]
    RETINA["macOS Retina\n2× DPI"]
    RESULT["Rendered ที่\n1040×1360 pixels\n(crisp pixel art)"]

    APP --> FLAG --> RETINA --> RESULT
```

---

## Typography

| ใช้งาน | Font | Size | Weight |
|--------|------|------|--------|
| ข้อความใน chat | `monospace` | 14px | regular |
| ชื่อผู้ส่ง | `monospace` | 14px | bold |
| placeholder input | `monospace` | 13px | regular |
| state label | `monospace` | 11px | regular |
