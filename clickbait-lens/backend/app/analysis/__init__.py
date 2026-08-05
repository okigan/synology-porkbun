from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import AnalysisResult, Analyzer
from .clickbait import PageContent
from .heuristic import HeuristicAnalyzer

__all__ = ["AnalysisResult", "Analyzer", "PageContent", "get_analyzer"]


@lru_cache
def get_analyzer() -> Analyzer:
    """Return the configured analyzer, defaulting to the LLM-free one."""
    if get_settings().analyzer == "llm":
        from .llm import LLMAnalyzer

        return LLMAnalyzer()
    return HeuristicAnalyzer()
