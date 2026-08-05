from __future__ import annotations

from datetime import date

from .base import AnalysisResult
from .claims import extract_claims
from .clickbait import PageContent, analyze_clickbait


class HeuristicAnalyzer:
    """Deterministic, offline, zero-dependency analysis. The default path."""

    name = "heuristic"

    def analyze(self, page: PageContent, reference: date | None = None) -> AnalysisResult:
        score, signals = analyze_clickbait(page)
        claims = extract_claims(page.body, title=page.title, reference=reference)
        return AnalysisResult(
            clickbait_score=score, signals=signals, claims=claims, analyzer=self.name
        )
