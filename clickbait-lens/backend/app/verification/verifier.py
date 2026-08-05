"""Turn live search results into a suggested resolution — without an LLM.

The pipeline is: build a query from the claim → fetch evidence → score each
result's stance toward the claim → aggregate into a verdict with a confidence.
Every step is inspectable, and the per-result stance and reason are returned so
a human can overrule the machine from the extension.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ..analysis.text import clamp, content_words, stems, words
from ..models import Claim, Resolution
from .base import SearchProvider, SearchResult, VerificationOutcome
from .providers import get_provider

SUPPORT_CUES: tuple[tuple[str, float], ...] = (
    ("as predicted", 0.9),
    ("came true", 0.9),
    ("proved right", 0.9),
    ("was right", 0.8),
    ("confirmed", 0.6),
    ("has now", 0.4),
    ("surpassed", 0.6),
    ("exceeded", 0.6),
    ("hit the target", 0.7),
    ("on track", 0.4),
    ("achieved", 0.5),
    ("materialised", 0.6),
    ("materialized", 0.6),
    ("indeed", 0.3),
)

REFUTE_CUES: tuple[tuple[str, float], ...] = (
    ("failed to", 0.8),
    ("did not", 0.6),
    ("never happened", 0.9),
    ("never materialised", 0.9),
    ("never materialized", 0.9),
    ("fell short", 0.8),
    ("was wrong", 0.9),
    ("proved wrong", 0.9),
    ("turned out to be false", 0.9),
    ("no evidence", 0.6),
    ("debunked", 0.9),
    ("abandoned", 0.6),
    ("scrapped", 0.6),
    ("cancelled", 0.6),
    ("canceled", 0.6),
    ("missed the target", 0.8),
    ("delayed", 0.4),
    ("postponed", 0.4),
    ("contrary to", 0.6),
    ("instead", 0.2),
    ("still has not", 0.7),
    ("yet to", 0.5),
)

#: Sources whose evidence counts for more. Deliberately short and editable —
#: a real deployment would source this from a maintained ratings list.
SOURCE_WEIGHTS: dict[str, float] = {
    "reuters.com": 1.3,
    "apnews.com": 1.3,
    "bbc.co.uk": 1.2,
    "bbc.com": 1.2,
    "ft.com": 1.2,
    "economist.com": 1.15,
    "nature.com": 1.3,
    "science.org": 1.3,
    "wikipedia.org": 0.9,
    "medium.com": 0.6,
    "reddit.com": 0.4,
    "x.com": 0.4,
    "twitter.com": 0.4,
}

STOP_QUERY_TERMS = frozenset(
    """will would could should might expect expects expected predict predicts predicted
    forecast forecasts projected project going set likely unlikely poised""".split()
)

_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|percent|per cent|billion|bn|million|m|trillion)?")
_UPPER_THRESHOLD = re.compile(
    r"\b(exceed|exceeds|surpass|surpasses|above|over|more than|at least|reach|reaches|top|tops)\b",
    re.IGNORECASE,
)
_LOWER_THRESHOLD = re.compile(
    r"\b(below|under|less than|fewer than|fall to|drop to|at most)\b", re.IGNORECASE
)

_MAGNITUDE = {
    "%": 1.0,
    "percent": 1.0,
    "per cent": 1.0,
    "": 1.0,
    "m": 1e6,
    "million": 1e6,
    "bn": 1e9,
    "billion": 1e9,
    "trillion": 1e12,
}


def _numbers(text: str) -> list[float]:
    """Quantities mentioned in ``text``, normalized to a base unit.

    Bare four-digit years are skipped — "exceed 40 percent by 2024" is a claim
    about 40, and letting 2024 through makes every threshold comparison wrong.
    """
    values: list[float] = []
    for raw, unit in _NUMBER.findall(text):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if not unit and value.is_integer() and 1900 <= value <= 2100 and "." not in raw:
            continue
        values.append(value * _MAGNITUDE.get(unit.lower().strip(), 1.0))
    return values


def build_query(claim: Claim, author_name: str | None = None) -> str:
    """Turn a claim sentence into a search query.

    Keeps the entities and the substantive terms, drops the prediction verbs
    (searching for "will" is useless) and adds the horizon year when known.
    """
    terms = [w for w in content_words(claim.text) if w not in STOP_QUERY_TERMS]
    entities = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*", claim.text)
    entities = [e for e in entities if len(e) > 3][:3]

    seen: set[str] = set()
    keywords: list[str] = []
    for token in entities + terms:
        low = token.lower()
        if low in seen:
            continue
        seen.add(low)
        keywords.append(token)
        if len(keywords) >= 9:
            break

    query = " ".join(keywords)
    if claim.target_date:
        query += f" {claim.target_date.year}"
    if author_name:
        query += f' "{author_name}"'
    return query.strip()


def score_stance(claim_text: str, result: SearchResult) -> tuple[float, str, float]:
    """Score one result: ``(stance, reason, relevance)``.

    Stance runs -1 (refutes the claim) to +1 (supports it); relevance is how
    much the result is actually about the claim.
    """
    haystack = f"{result.title}. {result.snippet}".lower()
    claim_stems = stems(content_words(claim_text))
    result_stems = stems(content_words(haystack))
    if not claim_stems:
        return 0.0, "claim has no substantive terms", 0.0

    relevance = len(claim_stems & result_stems) / len(claim_stems)
    if relevance < 0.15:
        return 0.0, "not topically related", relevance

    reasons: list[str] = []
    score = 0.0
    for phrase, weight in SUPPORT_CUES:
        if phrase in haystack:
            score += weight
            reasons.append(f"supports: '{phrase}'")
    for phrase, weight in REFUTE_CUES:
        if phrase in haystack:
            score -= weight
            reasons.append(f"refutes: '{phrase}'")

    numeric_reason = _numeric_stance(claim_text, haystack)
    if numeric_reason is not None:
        delta, reason = numeric_reason
        score += delta
        reasons.append(reason)

    stance = clamp(score / 1.5, -1.0, 1.0)
    return stance, "; ".join(reasons) or "topical but no directional cue", relevance


def _numeric_stance(claim_text: str, haystack: str) -> tuple[float, str] | None:
    """Compare a threshold claim against a number found in the evidence."""
    claim_numbers = _numbers(claim_text)
    evidence_numbers = _numbers(haystack)
    if not claim_numbers or not evidence_numbers:
        return None

    target = max(claim_numbers)
    actual = max(evidence_numbers)
    if target == 0:
        return None

    if _UPPER_THRESHOLD.search(claim_text):
        if actual >= target:
            return 0.7, f"evidence figure {actual:g} meets the claimed {target:g}"
        if actual < target * 0.85:
            return -0.7, f"evidence figure {actual:g} falls short of the claimed {target:g}"
    elif _LOWER_THRESHOLD.search(claim_text):
        if actual <= target:
            return 0.7, f"evidence figure {actual:g} is within the claimed {target:g}"
        if actual > target * 1.15:
            return -0.7, f"evidence figure {actual:g} exceeds the claimed ceiling {target:g}"
    return None


def _source_weight(result: SearchResult) -> float:
    domain = (result.source or "").lower()
    for known, weight in SOURCE_WEIGHTS.items():
        if domain.endswith(known):
            return weight
    return 1.0


def aggregate(results: list[SearchResult]) -> tuple[Resolution, float, str]:
    """Combine scored results into a resolution and a confidence."""
    scored = [r for r in results if abs(r.stance) > 0.05]
    if not scored:
        return (
            Resolution.unresolved,
            0.1,
            "No evidence clearly supported or refuted the claim.",
        )

    total_weight = 0.0
    weighted = 0.0
    for result in scored:
        weight = _source_weight(result)
        weighted += result.stance * weight
        total_weight += weight
    mean = weighted / total_weight

    # Disagreement between sources should lower confidence, not just average out.
    supporting = sum(1 for r in scored if r.stance > 0)
    refuting = len(scored) - supporting
    consensus = abs(supporting - refuting) / len(scored)
    volume = min(1.0, len(scored) / 4)
    confidence = round(clamp(abs(mean) * 0.6 + consensus * 0.25 + volume * 0.15), 2)

    if mean >= 0.55:
        resolution = Resolution.true
    elif mean >= 0.2:
        resolution = Resolution.mostly_true
    elif mean > -0.2:
        resolution = Resolution.mixed
    elif mean > -0.55:
        resolution = Resolution.mostly_false
    else:
        resolution = Resolution.false

    rationale = (
        f"{supporting} of {len(scored)} relevant results support the claim "
        f"(weighted stance {mean:+.2f})."
    )
    return resolution, confidence, rationale


async def verify_claim(
    claim: Claim,
    provider: SearchProvider | None = None,
    author_name: str | None = None,
    limit: int | None = None,
) -> VerificationOutcome:
    """Search the live web for evidence about ``claim`` and suggest a verdict."""
    from ..config import get_settings

    provider = provider or get_provider()
    limit = limit or get_settings().search_max_results
    query = build_query(claim, author_name)

    results = await provider.search(query, limit=limit)
    for result in results:
        stance, reason, relevance = score_stance(claim.text, result)
        result.stance = round(stance, 3)
        result.stance_reason = reason
        # Fold relevance into the stance so weakly-related pages count for less.
        result.stance = round(result.stance * clamp(0.4 + relevance, 0.0, 1.0), 3)

    if not results:
        return VerificationOutcome(
            suggested_resolution=Resolution.unverifiable.value,
            confidence=0.0,
            query=query,
            provider=provider.name,
            rationale="The search provider returned no results.",
            evidence=[],
        )

    resolution, confidence, rationale = aggregate(results)

    # A prediction whose deadline hasn't arrived can't be false yet. SQLite
    # hands back naive datetimes, so normalize before comparing.
    if claim.target_date is not None:
        deadline = claim.target_date
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline > datetime.now(UTC) and resolution in (
            Resolution.false,
            Resolution.mostly_false,
        ):
            rationale += " Deadline has not passed, so this is provisional."
            confidence = round(confidence * 0.6, 2)

    return VerificationOutcome(
        suggested_resolution=resolution.value,
        confidence=confidence,
        query=query,
        provider=provider.name,
        rationale=rationale,
        evidence=results,
    )


def summarize_evidence(results: list[SearchResult], max_terms: int = 6) -> list[str]:
    """Distinctive terms across the evidence — a cheap 'what did we find' line."""
    counts: dict[str, int] = {}
    for result in results:
        for token in set(words(result.snippet)):
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [term for term, count in ranked if count > 1][:max_terms]
