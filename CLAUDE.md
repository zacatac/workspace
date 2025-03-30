# Workspace Development Guide

## Commands
- **Install:** `uv pip install -e .`
- **Install dev dependencies:** `uv pip install -e ".[dev]"`
- **Run CLI:** `workspace [command] [options]` or `uv run workspace [command] [options]`
- **Test:** `uv run pytest tests/`
- **Test single file:** `uv run pytest tests/test_file.py`
- **Test single test:** `uv run pytest tests/test_file.py::TestClass::test_method`
- **Typecheck:** `uv run mypy workspace/`
- **Lint:** `uv run ruff check workspace/ tests/`
- **Format:** `uv run ruff format workspace/ tests/`
- **Fix auto-fixable lint issues:** `uv run ruff check --fix workspace/ tests/`

## Code Style
- **Formatting:** Ruff formatter with 100 character line length
- **Linting:** Ruff linter with various rules enabled
- **Imports:** Managed by Ruff isort plugin (standard library → third-party → local, alphabetized)
- **Types:** Full type annotations required (mypy strict mode)
- **Naming:** snake_case for variables/functions, PascalCase for classes
- **Documentation:** Google-style docstrings

## Error Handling
- Use custom exception classes extending from Exception
- Catch specific exceptions and re-raise with context
- Document exceptions in function docstrings

## Structure
- Core logic in workspace/core/
- CLI interface in workspace/cli/
- Utilities in workspace/utils/
- Tests mirror package structure in tests/