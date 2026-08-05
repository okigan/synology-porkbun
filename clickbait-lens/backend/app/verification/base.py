from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class SearchResult:
    """One piece of evidence retrieved from the web."""

    title: str
    url: str
    snippet: str
    source: str = ""
    published: str | None = None
    #: Set by the verifier: -1 (refutes) .. +1 (supports).
    stance: float = 0.0
    stance_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@runtime_checkable
class SearchProvider(Protocol):
    """A live evidence source.

    Implementations are async and must not raise on network failure — return an
    empty list and let the verifier report ``unverifiable``.
    """

    name: str

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]: ...


@dataclass
class VerificationOutcome:
    suggested_resolution: str
    confidence: float
    query: str
    provider: str
    rationale: str = ""
    evidence: list[SearchResult] = field(default_factory=list)
