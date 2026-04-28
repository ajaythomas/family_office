# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run dev server (hot reload)
uv run fastapi dev

# Add a dependency
uv add <package>

# Add a dev dependency (e.g. mypy, pytest)
uv add --dev <package>

# Type check
uv run mypy main.py

# Run tests
uv run pytest
```

## Architecture

Single-file FastAPI app. `main.py` is the entrypoint — it defines the `app` instance and all routes. `pyproject.toml` declares dependencies; `uv.lock` pins exact versions. Dependencies are managed exclusively via `uv`.
