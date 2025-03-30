# Workspace Development Guide

## Commands
- **Install:** `uv pip install -e .`
- **Run CLI:** `workspace [command] [options]` or `uv run workspace [command] [options]`
- **Test:** `uv run pytest tests/`
- **Test single file:** `uv run pytest tests/test_file.py`
- **Test single test:** `uv run pytest tests/test_file.py::TestClass::test_method`
- **Lint/Typecheck:** `uv run mypy workspace/`

## Code Style
- **Formatting:** Black with 100 character line length
- **Imports:** Use isort (standard library → third-party → local, alphabetized)
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