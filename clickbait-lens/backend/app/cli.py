"""Small CLI wrapper so `uv run clickbait-lens` starts the API."""

from __future__ import annotations

import uvicorn

from .config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info" if settings.seed_on_startup else "warning",
    )


if __name__ == "__main__":
    main()
