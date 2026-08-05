"""Runtime configuration.

Everything here has a working default so the service runs with no API keys and
no network access. Set environment variables (prefix ``CBL_``) to opt into the
live search providers or the optional LLM analyzer.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AnalyzerName = Literal["heuristic", "llm"]
SearchProviderName = Literal["fixture", "duckduckgo", "tavily", "brave"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CBL_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./clickbait_lens.db"

    # "heuristic" is the LLM-free default. "llm" is opt-in and requires the
    # `llm` extra plus ANTHROPIC_API_KEY.
    analyzer: AnalyzerName = "heuristic"
    llm_model: str = "claude-opus-5"
    anthropic_api_key: str | None = None

    # Live verification. "fixture" is offline/deterministic and is what the test
    # suite uses; "duckduckgo" is live and keyless; tavily/brave need keys.
    search_provider: SearchProviderName = "duckduckgo"
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    search_timeout_seconds: float = 10.0
    search_max_results: int = 8

    # CORS: the content script calls us from arbitrary article origins.
    allow_origins: list[str] = ["*"]

    seed_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
