"""Resolve bylines to :class:`~app.models.Author` rows.

Resolution order, most specific first:

1. An alias scoped to this outlet (``"J. Smith"`` at economist.com).
2. A global alias.
3. The canonical key derived from the normalized name.
4. Create a new author, and record the normalized name as a global alias.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Author, AuthorAlias
from .normalize import canonical_key, parse_byline


def _by_alias(session: Session, normalized: str, outlet_domain: str | None) -> Author | None:
    stmt = select(AuthorAlias).where(AuthorAlias.normalized_name == normalized)
    aliases = session.scalars(stmt).all()
    if not aliases:
        return None
    if outlet_domain:
        for alias in aliases:
            if alias.outlet_domain == outlet_domain:
                return alias.author
    for alias in aliases:
        if alias.outlet_domain is None:
            return alias.author
    return aliases[0].author


def resolve_author(
    session: Session,
    display_name: str,
    normalized: str,
    outlet_domain: str | None = None,
    create: bool = True,
) -> Author | None:
    author = _by_alias(session, normalized, outlet_domain)
    if author is not None:
        return author

    key = canonical_key(normalized)
    author = session.scalar(select(Author).where(Author.canonical_key == key))
    if author is not None:
        return author
    if not create:
        return None

    author = Author(
        canonical_key=key,
        display_name=display_name,
        primary_outlet_domain=outlet_domain,
    )
    author.aliases.append(
        AuthorAlias(normalized_name=normalized, outlet_domain=None, source="auto")
    )
    session.add(author)
    session.flush()
    return author


def resolve_authors(
    session: Session,
    byline: str,
    outlet_domain: str | None = None,
    create: bool = True,
) -> list[Author]:
    """Resolve every person named in ``byline`` to an author row."""
    authors: list[Author] = []
    for display_name, normalized in parse_byline(byline):
        author = resolve_author(session, display_name, normalized, outlet_domain, create=create)
        if author is not None and author not in authors:
            authors.append(author)
    return authors


def add_alias(
    session: Session,
    author: Author,
    normalized_name: str,
    outlet_domain: str | None = None,
    source: str = "manual",
) -> AuthorAlias:
    """Merge another byline spelling onto an existing author."""
    existing = session.scalar(
        select(AuthorAlias).where(
            AuthorAlias.normalized_name == normalized_name,
            AuthorAlias.outlet_domain == outlet_domain,
        )
    )
    if existing is not None:
        existing.author_id = author.id
        session.flush()
        session.refresh(author)
        return existing
    alias = AuthorAlias(
        normalized_name=normalized_name,
        outlet_domain=outlet_domain,
        source=source,
    )
    # Append through the relationship so the author's loaded collection stays
    # in sync — the session does not expire on commit.
    author.aliases.append(alias)
    session.flush()
    return alias
