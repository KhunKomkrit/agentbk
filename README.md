# 🤖 AgentBK

> **Desktop AI companion with a pixel art avatar** — Powered by multiple LLM providers, MCP tools, and RAG knowledge base

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Powered by pygame-ce](https://img.shields.io/badge/pygame--ce-2.5+-green.svg)](https://pyga.me/)

---

## 🎬 Screenshots

<div align="center">

### 🔄 Loading Experience
<img src="assets/images/screens/Screenshot 2569-03-29 at 13.29.52.png" width="300" alt="Loading Screen">

*Smooth initialization with progress tracking*

### 🏠 Main Interface
<img src="assets/images/screens/Screenshot 2569-03-29 at 13.29.54.png" width="300" alt="Main Screen">

*Pixel art avatar with expressive states*

### 💬 Chat Interface
<img src="assets/images/screens/Screenshot 2569-03-29 at 13.34.48.png" width="300" alt="Chat Screen">

*Stream responses with Thai language support*

### ⚙️ Settings Panel
<img src="assets/images/screens/Screenshot 2569-03-29 at 13.33.53.png" width="300" alt="Settings Screen">

*Multi-provider support (Ollama, Anthropic, OpenAI) + MCP Servers + RAG Knowledge Base*

</div>

---

## ✨ Features

### 🎨 **Pixel Art Avatar**
- **Expressive States**: IDLE (bobbing + blinking), THINKING (droopy eyes), TALKING (mouth animation), ERROR (X-eyes shake), LOADING (pulsing LED)
- **Procedural Rendering**: No sprites — all drawn with pygame primitives
- **Smooth Animations**: 60 FPS with interpolated transitions

### 🧠 **Multi-LLM Support**
- **Ollama Local** — Privacy-first, runs offline (qwen2.5-coder, llama3, etc.)
- **Anthropic Claude** — Advanced reasoning (Claude 3.5 Sonnet)
- **OpenAI GPT** — Industry standard (GPT-4, GPT-4 Turbo)
- **Dynamic Switching** — Change providers without restart

### 🔧 **MCP (Model Context Protocol) Integration**
- **Multi-Server Support** — Connect to multiple MCP servers simultaneously
- **Tool Management** — Enable/disable individual servers
- **Example**: Space MCP (NASA APIs) — Get ISS location, APOD, NEO data, planet info

### 📚 **RAG Knowledge Base**
- **Vector Search** — ChromaDB + sentence-transformers
- **Multi-Format** — Ingest PDF, TXT, MD files
- **Auto Context** — Inject relevant knowledge into conversations

### 🎙️ **Text-to-Speech**
- **Thai Voice** — edge-tts with Microsoft TH-PremwadeeNeural
- **macOS Fallback** — Native `say` command

### 🖥️ **Native macOS Integration**
- **Menubar Icon** — Quick access from system tray
- **Always On Top** — Float above other windows (toggleable)
- **Drag & Resize** — Borderless window with custom controls

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (tested on 3.14.2)
- **macOS** (for menubar integration) or **Linux/Windows** (partial support)
- **uv** package manager ([Install Guide](https://docs.astral.sh/uv/getting-started/installation/))

### Installation

```bash
# Clone the repository
git clone git@github.com:KhunKomkrit/agentbk.git
cd agentbk

# Install dependencies with uv
uv sync

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env` file with your API keys:

```bash
# LLM Provider (choose one or configure all)
ACTIVE_PROVIDER=ollama              # ollama | anthropic | openai

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI GPT
OPENAI_API_KEY=sk-...
```

### MCP Servers (Optional)

Create `~/.agentbk/mcp_servers.json`:

```json
[
  {
    "name": "Space MCP",
    "url": "http://localhost:8001/mcp",
    "enabled": true
  }
]
```

**Example MCP Server**: See [space-mcp](https://github.com/KhunKomkrit/space-mcp) for NASA APIs integration

### Run

```bash
# Start the application
uv run python -m app.main

# Development mode (with detailed logging)
DEV=1 uv run python -m app.main
```

---

## 📖 Usage

### Chat Interface

1. Click **Chat** button on main screen
2. Type your message in Thai or English
3. Avatar changes to THINKING state while processing
4. Responses stream in real-time
5. Click 🔗 icon when tools are used (MCP/built-in)

### Settings

- **LLM Provider**: Switch between Ollama/Anthropic/OpenAI
- **Model**: Select specific model (e.g., llama3, claude-3-5-sonnet)
- **Display**: Toggle "Always on top" mode
- **MCP Servers**: Enable/disable tool servers
- **Knowledge Base**: Add PDF/TXT/MD files for RAG

### Keyboard Shortcuts

- `Cmd+Q` — Quit application
- `Cmd+,` — Open Settings (planned)

---

## 🛠️ Development

### Project Structure

```
agentbk-01/
├── app/
│   ├── main.py              # Entry point, window management
│   ├── avatar/              # Pixel art rendering
│   │   └── renderer.py      # AvatarState, procedural drawing
│   ├── ui/                  # Scene system
│   │   ├── scene_manager.py # Scene stack (push/pop/replace)
│   │   ├── main_scene.py    # Avatar + navigation buttons
│   │   ├── chat_scene.py    # Chat history + input
│   │   └── settings_scene.py# Provider/MCP/RAG settings
│   ├── agent/               # AI brain
│   │   ├── router.py        # LLM streaming, tool routing
│   │   ├── memory.py        # Conversation persistence
│   │   ├── mcp_client.py    # Multi-MCP connection
│   │   └── tools.py         # Built-in tools (datetime, calc)
│   ├── providers/           # LLM adapters
│   │   ├── base.py          # BaseLLMProvider interface
│   │   ├── ollama_provider.py
│   │   ├── anthropic_provider.py
│   │   └── openai_provider.py
│   ├── rag/                 # Knowledge base
│   │   ├── embedder.py      # sentence-transformers
│   │   ├── store.py         # ChromaDB vector storage
│   │   └── ingestor.py      # PDF/TXT/MD parsing
│   └── tts/                 # Text-to-speech
│       └── speaker.py       # edge-tts + macOS say
└── docs/                    # Architecture documentation
```

### Run Tests

```bash
# Format & lint
uv run ruff check app/
uv run ruff format app/

# Type checking
uv run mypy app/

# Unit tests (planned)
uv run pytest tests/
```

### Add New MCP Server

1. Create MCP server (FastMCP, Python MCP SDK, or Node.js)
2. Expose HTTP endpoint (streamable-http transport)
3. Add to `~/.agentbk/mcp_servers.json`
4. Restart AgentBK — tools auto-loaded

### Add New LLM Provider

```bash
# Use slash command in .claude/commands/
/new-provider <provider-name>
```

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### Areas Looking for Help

- [ ] **Windows/Linux Support** — Remove macOS-specific dependencies (NSStatusItem, NSScreen)
- [ ] **Voice Input** — Add speech-to-text for voice conversations
- [ ] **Custom Avatars** — Support user-uploaded sprite sheets
- [ ] **Plugin System** — Hot-reload MCP servers without restart
- [ ] **Testing** — Add pytest coverage for core components
- [ ] **i18n** — Multi-language UI (currently TH/EN mixed)

### Development Workflow

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Follow code style (ruff + mypy)
4. Test changes: `DEV=1 uv run python -m app.main`
5. Commit: `git commit -m 'feat: add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open Pull Request

---

## 💖 Support This Project

AgentBK is **free and open source**. If you find it useful, consider supporting development:

### 🌟 Star This Repo
The easiest way to help — click ⭐ above!

### 💬 Spread the Word
Share on social media, write blog posts, or mention in your projects.

### 🐛 Report Bugs
Found an issue? [Open an issue](https://github.com/KhunKomkrit/agentbk/issues) with detailed steps to reproduce.

### 📝 Improve Documentation
Help make docs clearer — see [docs/](docs/) folder.

### ☕ Buy Me a Coffee (Optional)
If this project saved you time or brought value:

- **GitHub Sponsors**: [github.com/sponsors/KhunKomkrit](https://github.com/sponsors/KhunKomkrit)
- **Ko-fi**: [ko-fi.com/khunkomkrit](https://ko-fi.com/khunkomkrit)
- **Crypto (ETH)**: `0x...` *(coming soon)*

**Every star, issue report, and PR motivates us to build better tools!** 🚀

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file for details.

Free to use, modify, and distribute. Attribution appreciated but not required.

---

## 🙏 Acknowledgments

Built with amazing open-source tools:

- [pygame-ce](https://pyga.me/) — Modern SDL2 wrapper for Python
- [uv](https://docs.astral.sh/uv/) — Blazing fast Python package manager
- [FastMCP](https://github.com/jlowin/fastmcp) — Model Context Protocol servers
- [ChromaDB](https://www.trychroma.com/) — Vector database for RAG
- [edge-tts](https://github.com/rany2/edge-tts) — Microsoft Edge TTS
- [Heroicons](https://heroicons.com/) — Icon system

Special thanks to:
- Anthropic (Claude) for MCP specification
- Ollama team for local LLM runtime
- Thai AI community for feedback

---

## 🔗 Related Projects

- [space-mcp](https://github.com/KhunKomkrit/space-mcp) — NASA Space APIs MCP Server
- [pygame-ce](https://github.com/pygame-community/pygame-ce) — pygame Community Edition
- [FastMCP](https://github.com/jlowin/fastmcp) — Fast MCP server framework

---

<div align="center">

**Made with ❤️ in Thailand 🇹🇭**

[⬆ Back to Top](#-agentbk)

</div>
