Run lint and type checks on the codebase.

1. Ruff lint + autofix:
   `uv run ruff check --fix app/ tests/`

2. Ruff format check:
   `uv run ruff format --check app/ tests/`

3. Mypy type check:
   `uv run mypy app/ --ignore-missing-imports`

4. Report all errors grouped by file.
5. For each error: read the file at the reported line, diagnose, and propose a fix.
6. Apply fixes only after user confirmation.
