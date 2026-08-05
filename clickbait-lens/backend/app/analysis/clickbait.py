"""LLM-free clickbait / headline-integrity signals.

Each detector answers one narrow question and returns a :class:`Signal` with the
exact text it fired on, so the extension can highlight the offending sentence
rather than just showing a number.

The signals that matter most for "claims something is like that, but actually
isn't" are :func:`headline_body_divergence`, :func:`assertive_headline_hedged_body`
and :func:`attribution_stripped` — those compare the promise made by the headline
against what the body actually supports.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .text import (
    ATTRIBUTION_MARKERS,
    clamp,
    contains_any,
    content_words,
    hedge_ratio,
    sentences,
    stems,
    words,
)

CURIOSITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\byou won'?t believe\b", "withholds the payload"),
    (r"\bwhat happened next\b", "withholds the payload"),
    (r"\bthis is (?:why|what|how)\b", "promises an explanation without giving it"),
    (r"\bhere'?s (?:why|what|how)\b", "promises an explanation without giving it"),
    (r"\bthe (?:real )?reason (?:why|behind)\b", "promises an explanation without giving it"),
    (r"\bwill (?:shock|surprise|amaze) you\b", "emotional bait"),
    (r"\b(?:this|these|that) one (?:trick|thing|reason)\b", "vague referent"),
    (r"\bnobody is talking about\b", "manufactured exclusivity"),
    (r"\bgoes viral\b", "virality as the story"),
)

HYPE_TERMS: tuple[str, ...] = (
    "shock",
    "shocking",
    "shocked",
    "insane",
    "epic",
    "mind-blowing",
    "mindblowing",
    "jaw-dropping",
    "slams",
    "slammed",
    "destroys",
    "destroyed",
    "eviscerates",
    "obliterates",
    "annihilates",
    "brutal",
    "savage",
    "bombshell",
    "explosive",
    "stunning",
    "terrifying",
    "horrifying",
    "unbelievable",
    "incredible",
    "genius",
    "perfect",
    "flawless",
    "meltdown",
    "panic",
    "chaos",
    "crisis",
    "doomed",
    "collapse",
    "apocalypse",
    "war on",
    "secret",
    "exposed",
)

ABSOLUTES: tuple[str, ...] = (
    "always",
    "never",
    "everyone",
    "no one",
    "nobody",
    "every single",
    "all of",
    "the best",
    "the worst",
    "ever",
    "guaranteed",
    "definitely",
    "impossible",
)

VAGUE_AUTHORITY: tuple[str, ...] = (
    "experts say",
    "experts warn",
    "scientists say",
    "scientists warn",
    "studies show",
    "research shows",
    "analysts say",
    "sources say",
    "many believe",
    "some say",
    "critics say",
    "insiders say",
    "people are saying",
)

#: Sum of weighted severities that maps to a score of 100.
SATURATION = 3.0


@dataclass
class Evidence:
    text: str
    where: str  # "headline" | "body"
    note: str = ""


@dataclass
class Signal:
    id: str
    label: str
    severity: float  # 0..1, how bad this instance is
    weight: float  # relative importance in the aggregate score
    explanation: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PageContent:
    title: str
    body: str
    url: str = ""
    dek: str = ""

    @property
    def body_sentences(self) -> list[str]:
        return sentences(self.body)


def _headline_terms(page: PageContent) -> set[str]:
    return stems(content_words(page.title))


def curiosity_gap(page: PageContent) -> Signal | None:
    hits = [
        (m.group(0), note)
        for pattern, note in CURIOSITY_PATTERNS
        if (m := re.search(pattern, page.title, re.IGNORECASE))
    ]
    if not hits:
        return None
    return Signal(
        id="curiosity_gap",
        label="Curiosity gap",
        severity=clamp(0.55 + 0.2 * (len(hits) - 1)),
        weight=1.0,
        explanation="The headline promises information it deliberately withholds.",
        evidence=[Evidence(text=t, where="headline", note=note) for t, note in hits],
    )


def hype_lexicon(page: PageContent) -> Signal | None:
    found = [t for t in HYPE_TERMS if re.search(rf"\b{re.escape(t)}\b", page.title, re.IGNORECASE)]
    if not found:
        return None
    return Signal(
        id="hype_lexicon",
        label="Sensational wording",
        severity=clamp(0.35 + 0.25 * len(found)),
        weight=0.8,
        explanation="The headline leans on emotionally loaded verbs or adjectives.",
        evidence=[Evidence(text=t, where="headline") for t in found],
    )


def listicle(page: PageContent) -> Signal | None:
    m = re.match(r"^\s*(\d{1,2})\s+\w+", page.title)
    if not m:
        return None
    return Signal(
        id="listicle",
        label="Listicle framing",
        severity=0.35,
        weight=0.4,
        explanation="Numbered-list headlines optimise for clicks over substance.",
        evidence=[Evidence(text=m.group(0).strip(), where="headline")],
    )


def emotional_punctuation(page: PageContent) -> Signal | None:
    marks = re.findall(r"[!?]{2,}|!", page.title)
    shouty = re.findall(r"\b[A-Z]{4,}\b", page.title)
    if not marks and not shouty:
        return None
    return Signal(
        id="emotional_punctuation",
        label="Shouting",
        severity=clamp(0.25 * len(marks) + 0.3 * len(shouty)),
        weight=0.35,
        explanation="Exclamation marks or all-caps words used for emphasis.",
        evidence=[Evidence(text=t, where="headline") for t in (marks + shouty)],
    )


def unanswered_question(page: PageContent) -> Signal | None:
    """Betteridge check: a question headline whose body never resolves it."""
    if "?" not in page.title:
        return None
    key = _headline_terms(page)
    body_stems = stems(content_words(page.body))
    covered = len(key & body_stems) / len(key) if key else 0.0
    resolved = any(
        re.search(r"\b(yes|no|the answer is|it is not|it is|turns out)\b", s, re.IGNORECASE)
        for s in page.body_sentences[:20]
    )
    if covered > 0.6 and resolved:
        return None
    return Signal(
        id="unanswered_question",
        label="Question left unanswered",
        severity=clamp(0.4 + (1 - covered) * 0.5),
        weight=0.9,
        explanation="The headline poses a question the article never actually answers.",
        evidence=[Evidence(text=page.title, where="headline")],
    )


def absolutes(page: PageContent) -> Signal | None:
    found = [t for t in ABSOLUTES if re.search(rf"\b{re.escape(t)}\b", page.title, re.IGNORECASE)]
    if not found:
        return None
    return Signal(
        id="absolutes",
        label="Absolute claim",
        severity=clamp(0.3 + 0.2 * len(found)),
        weight=0.6,
        explanation="Headlines that admit no exceptions rarely survive the body text.",
        evidence=[Evidence(text=t, where="headline") for t in found],
    )


def vague_authority(page: PageContent) -> Signal | None:
    phrase = contains_any(page.title, VAGUE_AUTHORITY)
    if not phrase:
        return None
    # If the body names a specific source, the headline shorthand is defensible.
    named = re.search(
        r"\b(?:professor|dr\.?|according to)\s+[A-Z][a-z]+"
        r"|\b[A-Z][a-z]+\s+[A-Z][a-z]+,\s+(?:a|an|the)\s+\w+",
        page.body,
    )
    return Signal(
        id="vague_authority",
        label="Unnamed authority",
        severity=0.3 if named else 0.7,
        weight=0.7,
        explanation=(
            "The headline appeals to unnamed experts."
            + (" The body does name a source." if named else " The body never names one.")
        ),
        evidence=[Evidence(text=phrase, where="headline")],
    )


def headline_body_divergence(page: PageContent) -> Signal | None:
    """Headline talks about things the article never covers."""
    key = _headline_terms(page)
    if len(key) < 3:
        return None
    body_stems = stems(content_words(page.body))
    if not body_stems:
        return None
    missing = sorted(key - body_stems)
    ratio = len(missing) / len(key)
    if ratio < 0.34:
        return None
    return Signal(
        id="headline_body_divergence",
        label="Headline not supported by body",
        severity=clamp(ratio),
        weight=1.4,
        explanation=(
            f"{len(missing)} of {len(key)} substantive headline terms never appear in the article."
        ),
        evidence=[Evidence(text=w, where="headline", note="absent from body") for w in missing[:8]],
    )


def _topical_body_sentences(page: PageContent, limit: int = 6) -> list[str]:
    """Body sentences that share substantive terms with the headline, best first.

    This is the strict set: it answers "where does the article actually make the
    headline's claim?", which is what an attribution check needs.
    """
    key = _headline_terms(page)
    if not key:
        return []
    scored = []
    for s in page.body_sentences:
        overlap = len(key & stems(content_words(s)))
        if overlap:
            scored.append((overlap, s))
    scored.sort(key=lambda pair: (-pair[0], len(pair[1])))
    return [s for _, s in scored[:limit]]


def _supporting_sentences(page: PageContent, limit: int = 8) -> list[str]:
    """The passages a reader would take as backing the headline.

    The lede counts even when it shares no vocabulary with the headline — news
    articles put the headline's thesis in the first paragraph, often in
    different words.
    """
    lede = page.body_sentences[:3]
    supporting = list(lede)
    for sentence in _topical_body_sentences(page, limit):
        if sentence not in supporting:
            supporting.append(sentence)
    return supporting[:limit]


def assertive_headline_hedged_body(page: PageContent) -> Signal | None:
    """The headline states it flatly; the body only says it might be so."""
    if hedge_ratio(page.title) > 0.15:
        return None  # headline already hedges — no mismatch
    supporting = _supporting_sentences(page)
    if len(supporting) < 2:
        return None

    hedged = [s for s in supporting if hedge_ratio(s) >= 0.3]
    # Mean density rather than a count ratio: one heavily hedged passage among
    # short factual ones is still a mismatch, and a single stray "may" is not.
    mean_hedge = sum(hedge_ratio(s) for s in supporting) / len(supporting)
    if len(hedged) < 2 or mean_hedge < 0.2:
        return None

    return Signal(
        id="assertive_headline_hedged_body",
        label="Stated as fact, hedged in the text",
        severity=clamp(0.4 + mean_hedge),
        weight=1.5,
        explanation=(
            "The headline asserts this outright, but the passages that back it up are hedged "
            "with words like 'may', 'could' or 'suggests'."
        ),
        evidence=[Evidence(text=page.title, where="headline", note="asserted without hedging")]
        + [Evidence(text=s, where="body", note="hedged support") for s in hedged[:4]],
    )


def attribution_stripped(page: PageContent) -> Signal | None:
    """Someone else's claim presented as the publication's own finding."""
    if contains_any(page.title, ATTRIBUTION_MARKERS):
        return None  # headline already attributes it
    if re.search(r"[:,]\s*\w+\s+(?:says|said|claims)\s*$", page.title, re.IGNORECASE):
        return None
    topical = _topical_body_sentences(page)
    attributed = [s for s in topical if contains_any(s, ATTRIBUTION_MARKERS)]
    if not attributed or len(attributed) / len(topical) < 0.5:
        return None
    return Signal(
        id="attribution_stripped",
        label="Attribution dropped from headline",
        severity=clamp(0.45 + 0.4 * (len(attributed) / len(topical))),
        weight=1.3,
        explanation=(
            "In the body this is something a source claims, but the headline presents it as "
            "established fact."
        ),
        evidence=[Evidence(text=page.title, where="headline", note="unattributed")]
        + [Evidence(text=s, where="body", note="attributed to a source") for s in attributed[:4]],
    )


def thin_body(page: PageContent) -> Signal | None:
    n = len(words(page.body))
    if n >= 220 or n == 0:
        return None
    return Signal(
        id="thin_body",
        label="Thin article",
        severity=clamp((220 - n) / 220),
        weight=0.5,
        explanation=f"The article body is only about {n} words long.",
        evidence=[Evidence(text=f"{n} words", where="body")],
    )


DETECTORS = (
    curiosity_gap,
    hype_lexicon,
    listicle,
    emotional_punctuation,
    unanswered_question,
    absolutes,
    vague_authority,
    headline_body_divergence,
    assertive_headline_hedged_body,
    attribution_stripped,
    thin_body,
)


def analyze_clickbait(page: PageContent) -> tuple[float, list[Signal]]:
    """Return a 0-100 score and the signals that produced it."""
    signals = [s for detector in DETECTORS if (s := detector(page)) is not None]
    total = sum(s.severity * s.weight for s in signals)
    score = round(100 * clamp(total / SATURATION), 1)
    signals.sort(key=lambda s: -(s.severity * s.weight))
    return score, signals


def verdict_for(score: float) -> str:
    if score >= 65:
        return "high"
    if score >= 35:
        return "moderate"
    if score >= 15:
        return "low"
    return "clean"
