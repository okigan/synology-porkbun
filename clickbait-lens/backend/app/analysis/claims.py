"""LLM-free claim extraction.

Pulls out the sentences that are actually *scoreable* — falsifiable predictions
first, then checkable factual assertions — and discards editorialising. Only
extracted claims can ever contribute to an author's track record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from ..models import ClaimKind
from .text import clamp, contains_any, hedge_ratio, sentences, words

PREDICTION_CUES: tuple[str, ...] = (
    "will",
    "won't",
    "will not",
    "shall",
    "is going to",
    "are going to",
    "is set to",
    "are set to",
    "is expected to",
    "are expected to",
    "expects",
    "expect",
    "forecast",
    "forecasts",
    "predict",
    "predicts",
    "predicted",
    "project",
    "projects",
    "projected",
    "anticipate",
    "anticipates",
    "on track to",
    "poised to",
    "likely to",
    "unlikely to",
    "due to reach",
    "should reach",
    "by the end of",
    "in the coming",
    "over the next",
)

#: Sentences about the past that merely *report* someone else's forecast are not
#: the author's own prediction.
PREDICTION_ANTIPATTERNS: tuple[str, ...] = (
    "had predicted",
    "previously predicted",
    "once predicted",
    "had forecast",
    "was expected to",
    "were expected to",
)

OPINION_CUES: tuple[str, ...] = (
    "i think",
    "i believe",
    "in my view",
    "it seems to me",
    "arguably",
    "surely",
    "of course",
    "regrettably",
    "thankfully",
    "absurd",
    "outrageous",
    "brilliant",
    "disgraceful",
    "wonderful",
    "terrible",
    "ought to",
    "should be ashamed",
)

_NUMERIC = re.compile(r"\b\d[\d,.]*\s*(?:%|percent|per cent|bn|billion|m|million|trillion|k)?\b")
_YEAR = re.compile(r"\b(20\d{2}|19\d{2})\b")

_HORIZON_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bby (?:the end of )?(20\d{2})\b", re.I), "year"),
    (re.compile(r"\bin (20\d{2})\b", re.I), "year"),
    (re.compile(r"\bby (?:the end of )?(?:this|the) (decade)\b", re.I), "decade"),
    (re.compile(r"\bwithin (?:the next )?(\w+) (year|years|month|months)\b", re.I), "relative"),
    (re.compile(r"\bover the next (\w+) (year|years|month|months|decade)\b", re.I), "relative"),
    (re.compile(r"\b(next year|this year|next month|next decade)\b", re.I), "named"),
)

_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "a": 1,
    "an": 1,
    "few": 3,
    "several": 4,
    "couple": 2,
}


@dataclass
class ExtractedClaim:
    text: str
    kind: ClaimKind
    assertiveness: float
    extraction_confidence: float
    horizon_text: str | None = None
    target_date: datetime | None = None
    cues: list[str] = field(default_factory=list)


def _to_int(token: str) -> int | None:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token)


def parse_horizon(
    sentence: str, reference: date | None = None
) -> tuple[str | None, datetime | None]:
    """Extract a resolution deadline from a prediction sentence."""
    ref = reference or datetime.now(UTC).date()
    for pattern, kind in _HORIZON_PATTERNS:
        m = pattern.search(sentence)
        if not m:
            continue
        phrase = m.group(0)
        if kind == "year":
            return phrase, datetime(int(m.group(1)), 12, 31, tzinfo=UTC)
        if kind == "decade":
            end = (ref.year // 10) * 10 + 9
            return phrase, datetime(end, 12, 31, tzinfo=UTC)
        if kind == "relative":
            n = _to_int(m.group(1))
            if n is None:
                return phrase, None
            unit = m.group(2).lower()
            if unit.startswith("month"):
                year = ref.year + (ref.month - 1 + n) // 12
                month = (ref.month - 1 + n) % 12 + 1
                return phrase, datetime(year, month, 28, tzinfo=UTC)
            if unit.startswith("decade"):
                return phrase, datetime(ref.year + 10 * n, 12, 31, tzinfo=UTC)
            return phrase, datetime(ref.year + n, 12, 31, tzinfo=UTC)
        low = phrase.lower()
        if low == "next year":
            return phrase, datetime(ref.year + 1, 12, 31, tzinfo=UTC)
        if low == "this year":
            return phrase, datetime(ref.year, 12, 31, tzinfo=UTC)
        if low == "next decade":
            return phrase, datetime(ref.year + 10, 12, 31, tzinfo=UTC)
        if low == "next month":
            year = ref.year + (1 if ref.month == 12 else 0)
            month = 1 if ref.month == 12 else ref.month + 1
            return phrase, datetime(year, month, 28, tzinfo=UTC)
    m = _YEAR.search(sentence)
    if m and int(m.group(1)) > ref.year:
        return m.group(0), datetime(int(m.group(1)), 12, 31, tzinfo=UTC)
    return None, None


def _prediction_cues(sentence: str) -> list[str]:
    low = sentence.lower()
    if contains_any(low, PREDICTION_ANTIPATTERNS):
        return []
    return [c for c in PREDICTION_CUES if re.search(rf"\b{re.escape(c)}\b", low)]


def classify(sentence: str, reference: date | None = None) -> ExtractedClaim | None:
    """Classify one sentence, or return None if it is not worth tracking."""
    token_count = len(words(sentence))
    if token_count < 6 or token_count > 90:
        return None

    hedging = hedge_ratio(sentence)
    assertiveness = clamp(1.0 - hedging)
    opinion_cue = contains_any(sentence, OPINION_CUES)
    cues = _prediction_cues(sentence)

    if cues:
        horizon_text, target_date = parse_horizon(sentence, reference)
        confidence = clamp(0.45 + 0.15 * len(cues) + (0.2 if horizon_text else 0.0))
        if opinion_cue:
            confidence = clamp(confidence - 0.15)
        return ExtractedClaim(
            text=sentence,
            kind=ClaimKind.prediction,
            assertiveness=assertiveness,
            extraction_confidence=confidence,
            horizon_text=horizon_text,
            target_date=target_date,
            cues=cues,
        )

    if opinion_cue:
        return ExtractedClaim(
            text=sentence,
            kind=ClaimKind.opinion,
            assertiveness=assertiveness,
            extraction_confidence=0.5,
            cues=[opinion_cue],
        )

    has_number = bool(_NUMERIC.search(sentence))
    has_year = bool(_YEAR.search(sentence))
    if has_number or has_year:
        return ExtractedClaim(
            text=sentence,
            kind=ClaimKind.factual,
            assertiveness=assertiveness,
            extraction_confidence=clamp(
                0.4 + (0.2 if has_number else 0) + (0.1 if has_year else 0)
            ),
            cues=["quantified"],
        )
    return None


def extract_claims(
    body: str,
    title: str = "",
    reference: date | None = None,
    max_claims: int = 40,
) -> list[ExtractedClaim]:
    """Extract claims from an article body, best (most scoreable) first."""
    claims: list[ExtractedClaim] = []
    seen: set[str] = set()

    if title:
        title_cues = _prediction_cues(title)
        if title_cues:
            horizon_text, target_date = parse_horizon(title, reference)
            claims.append(
                ExtractedClaim(
                    text=title.strip(),
                    kind=ClaimKind.headline_promise,
                    assertiveness=clamp(1.0 - hedge_ratio(title)),
                    extraction_confidence=0.7,
                    horizon_text=horizon_text,
                    target_date=target_date,
                    cues=title_cues,
                )
            )
            seen.add(title.strip().lower())

    for sentence in sentences(body):
        key = sentence.lower()
        if key in seen:
            continue
        claim = classify(sentence, reference)
        if claim is None:
            continue
        seen.add(key)
        claims.append(claim)

    priority = {
        ClaimKind.headline_promise: 0,
        ClaimKind.prediction: 1,
        ClaimKind.factual: 2,
        ClaimKind.opinion: 3,
    }
    claims.sort(key=lambda c: (priority[c.kind], -c.extraction_confidence))
    return claims[:max_claims]
