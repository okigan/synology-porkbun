"""Small, dependency-free text utilities shared by the analyzers.

Deliberately not a full NLP stack: the point of the heuristic path is that it
runs anywhere, instantly, with no model download and no API key.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_SENTENCE_END = re.compile(r"(?<=[.!?])[\s ]+(?=[\"'“(\[]?[A-Z0-9])")
_WORD = re.compile(r"[a-z0-9][a-z0-9'’\-]*")

STOPWORDS: frozenset[str] = frozenset(
    """
a about above after again against all am an and any are aren't as at be because been before being
below between both but by can cannot could couldn't did didn't do does doesn't doing don't down
during each few for from further had hadn't has hasn't have haven't having he her here hers herself
him himself his how i if in into is isn't it its itself just me more most my myself no nor not of
off on once only or other ought our ours ourselves out over own same shan't she should shouldn't so
some such than that the their theirs them themselves then there these they this those through to
too under until up very was wasn't we were weren't what when where which while who whom why with
won't would wouldn't you your yours yourself yourselves s t don now also new says said say
""".split()
)

#: Words that soften an assertion. Used both for hedge detection and for the
#: headline-assertive / body-hedged divergence signal.
HEDGE_TERMS: frozenset[str] = frozenset(
    """
may might could possibly perhaps probably likely unlikely apparently reportedly allegedly seemingly
suggests suggest indicates indicate appears appear potential potentially arguably roughly around
approximately estimated estimate some many several often sometimes tends tend believed thought
speculation rumoured rumored purportedly ostensibly presumably conceivably
""".split()
)

#: Verbs/markers that attribute a statement to someone other than the writer.
ATTRIBUTION_MARKERS: tuple[str, ...] = (
    "according to",
    "claims",
    "claimed",
    "alleges",
    "alleged",
    "says",
    "said",
    "told reporters",
    "reportedly",
    "sources say",
    "critics say",
    "supporters say",
    "in a statement",
    "argues",
    "argued",
    "suggests",
    "suggest",
    "insists",
    "insist",
    "warns",
    "denies",
    "denied",
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[\s ]+", " ", text or "").strip()


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def sentences(text: str) -> list[str]:
    """Split prose into sentences.

    Handles the abbreviation cases that actually show up in news copy (titles,
    ``U.S.``, ``Inc.``) rather than attempting general correctness.
    """
    text = normalize_whitespace(text)
    if not text:
        return []
    protected = text
    for abbr in ("Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "St.", "Inc.", "Ltd.", "vs."):
        protected = protected.replace(abbr, abbr.replace(".", "\x00"))
    # Not a raw string: the replacement carries a literal NUL as the placeholder.
    protected = re.sub(r"\b([A-Z])\.(?=[A-Z]\.)", "\\1\x00", protected)
    parts = _SENTENCE_END.split(protected)
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


def words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def content_words(text: str) -> list[str]:
    return [w for w in words(strip_accents(text)) if w not in STOPWORDS and len(w) > 2]


def stem(word: str) -> str:
    """Crude suffix stripper, enough to match ``collapse``/``collapsed``."""
    for suffix in (
        "ational",
        "ization",
        "iveness",
        "ingly",
        "edly",
        "ments",
        "ment",
        "ness",
        "ions",
        "ing",
        "ies",
        "ied",
        "ers",
        "er",
        "ed",
        "es",
        "s",
    ):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def stems(items: Iterable[str]) -> set[str]:
    return {stem(w) for w in items}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def contains_any(text: str, needles: Iterable[str]) -> str | None:
    """Return the first needle present in ``text`` (case-insensitive), else None."""
    low = text.lower()
    for needle in needles:
        if needle in low:
            return needle
    return None


def hedge_ratio(text: str) -> float:
    """Fraction of content words that are hedges, clamped to a readable range."""
    toks = words(text)
    if not toks:
        return 0.0
    hits = sum(1 for t in toks if t in HEDGE_TERMS)
    return min(1.0, hits / max(6, len(toks)) * 6)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
