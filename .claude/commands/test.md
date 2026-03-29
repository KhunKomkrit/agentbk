Run the test suite.

Usage: `/test` or `/test --all`

Steps:
1. Default — unit tests only (no real API calls):
   `uv run python -m pytest tests/ -m "not integration" -v`

2. If `$ARGUMENTS` contains `--all` — full suite including integration:
   `uv run python -m pytest tests/ -v`
   (requires .env with valid API keys)

3. Show pass/fail summary.
4. For each failing test:
   - Read the test file
   - Read the source file it tests
   - Diagnose root cause
   - Propose fix — ask user before applying
