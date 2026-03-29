# AgentBK-01 — Documentation Index

> Desktop AI Bot พร้อม Pixel Avatar สำหรับ macOS/PC พัฒนาด้วย Python

---

## เอกสารทั้งหมด

| ไฟล์ | เนื้อหา |
|------|---------|
| [01-architecture.md](./01-architecture.md) | System architecture, component diagram, data flow |
| [02-ui-design.md](./02-ui-design.md) | Layout, visual design, color system, UI states |
| [03-avatar-system.md](./03-avatar-system.md) | Bot face avatar, animation states, rendering pipeline |
| [04-llm-providers.md](./04-llm-providers.md) | Provider pattern, adapter interface, tool calling |
| [05-dev-guide.md](./05-dev-guide.md) | Setup, conventions, workflow, testing |
| [06-agent-tools.md](./06-agent-tools.md) | Conversation memory, built-in tools, tool loop |
| [07-mcp-rag.md](./07-mcp-rag.md) | Multi-MCP config, RAG knowledge base, vector search |

---

## ภาพรวมโปรเจกต์

```mermaid
mindmap
  root((AgentBK-01))
    UI Layer
      Bot Face Avatar
        IDLE bob + blink
        THINKING droopy eyes
        TALKING mouth flap
        ERROR X-eyes shake
      Chat Panel
        Streaming bubbles
        Tool indicator pill
        Thai text wrap
      Settings
        Provider selector
        MCP Servers list (N servers)
        Knowledge Base file manager
        Danger Zone clear history
    Agent Core
      Router
        stream_tools single-pass
        Keyword routing fast path
        KV-cache warmup
        RAG context injection
      Memory
        Persistent JSON
        Rolling 100 messages
      Tools
        get_datetime
        calculate
        get_weather stub
      Multi-MCP
        JSON config file
        N servers parallel
        enable/disable per server
      RAG Knowledge Base
        sentence-transformers
        ChromaDB vector store
        PDF TXT MD ingest
    Icon System
      Heroicons SVG
      SVG path parser
      pygame Surface tinting
    LLM Providers
      Ollama Local
      Anthropic Claude
      OpenAI GPT
    TTS
      edge-tts Thai voice
      macOS say fallback
    macOS
      menubar NSStatusItem
      always-on-top SDL2
      drag and resize
```

---

## Tech Stack

```mermaid
graph LR
    PY["Python 3.11+"]
    PG["pygame-ce"]
    OAI["openai SDK\n(Ollama-compat)"]
    PIL["Pillow\n(icon rendering)"]
    DOT["python-dotenv"]
    UV["uv package manager"]

    PY --> PG
    PY --> OAI
    PY --> PIL
    PY --> DOT
    UV -->|manages| PY
```

---

## สถานะโปรเจกต์

| Phase | เนื้อหา | สถานะ |
|-------|---------|-------|
| Phase 1 | UI — avatar, scenes, drag/resize, Thai font | ✅ Done |
| Phase 2 | LLM providers, AgentRouter, bot face avatar, SVG icons, menubar icon | ✅ Done |
| Phase 3 | Conversation memory, tool calling, built-in tools, Danger Zone | ✅ Done |
| Phase 4 | Real weather API, Anthropic/OpenAI providers, MCP client, TTS | ✅ Done |
| Phase 5 | Performance — stream_tools(), keyword routing, KV-cache warmup | ✅ Done |
| Phase 6 | Multi-MCP (N servers, JSON config) + RAG knowledge base (ChromaDB + sentence-transformers) | ✅ Done |

```mermaid
gantt
    title AgentBK-01 Development Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1 — UI
        Pixel avatar + scenes        :done, p1a, 2026-03-28, 1d
        Main window drag/resize      :done, p1b, 2026-03-28, 1d
        Settings + Thai font         :done, p1c, 2026-03-28, 1d
    section Phase 2 — LLM
        Ollama provider              :done, p2a, 2026-03-28, 1d
        AgentRouter + queue stream   :done, p2b, 2026-03-28, 1d
        Bot face avatar redesign     :done, p2c, 2026-03-28, 1d
        SVG icon system              :done, p2d, 2026-03-28, 1d
        macOS menubar avatar icon    :done, p2e, 2026-03-28, 1d
    section Phase 3 — Agent
        Conversation memory (JSON)   :done, p3a, 2026-03-28, 1d
        Tool calling loop            :done, p3b, 2026-03-28, 1d
        Built-in tools               :done, p3c, 2026-03-28, 1d
        Settings Danger Zone         :done, p3d, 2026-03-28, 1d
    section Phase 4 — Polish
        Anthropic / OpenAI providers :done, p4a, 2026-03-29, 1d
        Real weather API (wttr.in)   :done, p4b, 2026-03-29, 1d
        MCP client integration       :done, p4c, 2026-03-29, 1d
        TTS voice output             :done, p4d, 2026-03-29, 1d
    section Phase 5 — Performance
        stream_tools() single-pass   :done, p5a, 2026-03-29, 1d
        Keyword routing fast path    :done, p5b, 2026-03-29, 1d
        KV-cache warmup              :done, p5c, 2026-03-29, 1d
    section Phase 6 — Multi-MCP + RAG
        mcp_config.py JSON store     :done, p6a, 2026-03-29, 1d
        Multi-MCPClient list         :done, p6b, 2026-03-29, 1d
        Settings MCP list UI         :done, p6c, 2026-03-29, 1d
        RAG embedder + chunker       :done, p6d, 2026-03-29, 1d
        ChromaDB store + ingestor    :done, p6e, 2026-03-29, 1d
        RAG injection in router      :done, p6f, 2026-03-29, 1d
        Settings Knowledge Base UI   :done, p6g, 2026-03-29, 1d
```
