Run the AgentBK desktop app.

1. Check `.env` exists — if not, tell user: `cp .env.example .env` then fill in API keys
2. Verify `uv.lock` is up to date: `uv sync`
3. Launch: `uv run python -m app.main`
4. If ImportError for pygame → `uv sync` first
5. If `No video mode` error → must run in a GUI session (not SSH)
