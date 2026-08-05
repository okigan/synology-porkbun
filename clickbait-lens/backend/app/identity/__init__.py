from .normalize import (
    canonical_key,
    looks_like_person,
    normalize_name,
    parse_byline,
    split_byline,
)
from .resolver import resolve_authors

__all__ = [
    "canonical_key",
    "looks_like_person",
    "normalize_name",
    "parse_byline",
    "resolve_authors",
    "split_byline",
]
