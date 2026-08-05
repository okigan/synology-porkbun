from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from .claims import ExtractedClaim
from .clickbait import PageContent, Signal


@dataclass
class AnalysisResult:
    clickbait_score: float
    signals: list[Signal] = field(default_factory=list)
    claims: list[ExtractedClaim] = field(default_factory=list)
    analyzer: str = "heuristic"


@runtime_checkable
class Analyzer(Protocol):
    """Swappable analysis backend.

    The heuristic implementation is the default and the target end state; the
    LLM implementation exists so quality can be compared against it while the
    rule set is being built out.
    """

    name: str

    def analyze(self, page: PageContent, reference: date | None = None) -> AnalysisResult: ...
