"""Byline normalization.

Bylines are messy: ``By JANE Q. SMITH and Bob Lee, Senior Correspondent`` has to
collapse onto the same identity as ``Jane Smith``. This module does the string
work; :mod:`app.identity.resolver` does the database side, including the alias
table that merges spellings normalization alone can't.
"""

from __future__ import annotations

import re

from ..analysis.text import normalize_whitespace, strip_accents

HONORIFICS = frozenset(
    """mr mrs ms miss dr prof professor sir dame lord lady rev fr sr jr phd md
    esq hon rt""".split()
)

#: Trailing job titles that appear inside bylines and are not part of the name.
TITLE_SUFFIXES = (
    "senior correspondent",
    "correspondent",
    "staff writer",
    "editor at large",
    "editor-at-large",
    "contributing editor",
    "senior editor",
    "managing editor",
    "editor",
    "columnist",
    "reporter",
    "analyst",
    "bureau chief",
    "special correspondent",
)

_BYLINE_PREFIX = re.compile(r"^\s*(by|written by|words by|reporting by)[\s:]+", re.IGNORECASE)
_SEPARATORS = re.compile(r"\s*(?:,|;|\band\b|&|\bwith\b|/|\|)\s*", re.IGNORECASE)
_NON_NAME = re.compile(r"[^a-z\s'\-]")
_LOCATION_TAIL = re.compile(r"\s+in\s+[A-Z][a-z]+.*$")


def _strip_titles(fragment: str) -> str:
    low = fragment.lower()
    for title in TITLE_SUFFIXES:
        if low == title or low.endswith(" " + title) or low.startswith(title + " "):
            low = low.replace(title, " ")
    return normalize_whitespace(low)


def split_byline(byline: str) -> list[str]:
    """Split a raw byline into individual name fragments.

    ``"By Jane Smith and Bob Lee, Senior Correspondent"`` →
    ``["Jane Smith", "Bob Lee"]``
    """
    if not byline:
        return []
    text = _BYLINE_PREFIX.sub("", normalize_whitespace(byline))
    text = _LOCATION_TAIL.sub("", text)
    parts = [p for p in (_strip_titles(f) for f in _SEPARATORS.split(text)) if p]
    return [p for p in parts if looks_like_person(p)]


def looks_like_person(fragment: str) -> bool:
    """Filter out ``Staff``, ``Our Correspondent``, agency credits, and noise."""
    cleaned = normalize_whitespace(fragment).lower()
    if not cleaned or len(cleaned) < 4 or len(cleaned) > 60:
        return False
    if cleaned in {"staff", "editorial board", "the editors", "admin", "newsroom"}:
        return False
    if any(
        agency in cleaned for agency in ("reuters", "associated press", "afp", "bloomberg news")
    ):
        return False
    tokens = [t for t in _NON_NAME.sub(" ", cleaned).split() if t not in HONORIFICS]
    # A person's byline is at least a first and last name.
    return len(tokens) >= 2


def normalize_name(name: str) -> str:
    """Fold a name to its comparable form: ``"Jane Q. Smith"`` → ``"jane q smith"``."""
    text = strip_accents(normalize_whitespace(name)).lower()
    if "," in text:  # "Smith, Jane" → "Jane Smith"
        last, _, first = text.partition(",")
        text = f"{first.strip()} {last.strip()}"
    tokens = [t for t in _NON_NAME.sub(" ", text).split() if t and t not in HONORIFICS]
    return " ".join(tokens)


def canonical_key(name: str) -> str:
    """Slug used as the author's stable identity key across outlets."""
    return normalize_name(name).replace(" ", "-")


def parse_byline(byline: str) -> list[tuple[str, str]]:
    """Return ``(display_name, normalized_name)`` pairs for a raw byline."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for fragment in split_byline(byline):
        normalized = normalize_name(fragment)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append((_titleize(fragment), normalized))
    return results


def _titleize(fragment: str) -> str:
    def fix(word: str) -> str:
        if "-" in word:
            return "-".join(fix(p) for p in word.split("-"))
        if word.startswith(("mc", "mac")) and len(word) > 3:
            head = 2 if word.startswith("mc") else 3
            return word[:head].capitalize() + word[head:].capitalize()
        if word.startswith("o'") and len(word) > 2:
            return "O'" + word[2:].capitalize()
        return word.capitalize()

    return " ".join(fix(w) for w in normalize_whitespace(fragment).lower().split())
