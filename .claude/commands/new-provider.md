Scaffold a new LLM provider adapter.

Usage: `/new-provider <name>` (e.g. `/new-provider groq`)

Steps:
1. Read `app/providers/base.py` to get the current BaseLLMProvider interface
2. Create `app/providers/<name>_provider.py` implementing:
   - `name: str = "<name>"`
   - `model: str = "<default model>"`
   - `async def chat(self, messages, **kwargs) -> str`
   - `async def stream(self, messages, **kwargs) -> AsyncIterator[str]`
   - Proper error handling (AuthenticationError, RateLimitError, ConnectionError)
3. Register the new provider in `app/providers/__init__.py` ProviderFactory
4. Add required env vars to `.env.example`
5. Add the provider to the `_PROVIDERS` / `_MODELS` lists in `app/ui/settings_scene.py`
6. Update `docs/04-llm-providers.md` with a row in the comparison table

Follow the same async/streaming pattern as `app/providers/anthropic_provider.py`.
