from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..identity import normalize_name
from ..identity.resolver import add_alias
from ..models import Article, Author, Claim
from ..schemas import AliasRequest, AuthorDetail, AuthorSummary
from ..services import article_brief, author_summary, claim_out, trust_for

router = APIRouter(prefix="/authors", tags=["authors"])


def _get(session: Session, author_id: int) -> Author:
    author = session.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="author not found")
    return author


@router.get("", response_model=list[AuthorSummary])
def list_authors(
    session: Session = Depends(get_session),
    name: str | None = Query(default=None, description="Byline to look up."),
    outlet: str | None = Query(default=None, description="Outlet domain filter."),
    limit: int = Query(default=25, le=100),
) -> list[AuthorSummary]:
    stmt = select(Author)
    if name:
        normalized = normalize_name(name)
        key = normalized.replace(" ", "-")
        stmt = stmt.where(Author.canonical_key.contains(key.split("-")[-1]))
    if outlet:
        stmt = stmt.where(Author.primary_outlet_domain == outlet)
    authors = session.scalars(stmt.limit(limit)).all()
    return [author_summary(session, a) for a in authors]


@router.get("/{author_id}", response_model=AuthorDetail)
def get_author(author_id: int, session: Session = Depends(get_session)) -> AuthorDetail:
    author = _get(session, author_id)
    claims = session.scalars(
        select(Claim)
        .where(Claim.author_id == author.id)
        .order_by(Claim.created_at.desc())
        .limit(50)
    ).all()
    articles = session.scalars(
        select(Article)
        .join(Article.authors)
        .where(Author.id == author.id)
        .order_by(Article.fetched_at.desc())
        .limit(25)
    ).all()
    return AuthorDetail(
        id=author.id,
        canonical_key=author.canonical_key,
        display_name=author.display_name,
        primary_outlet_domain=author.primary_outlet_domain,
        bio=author.bio,
        trust=trust_for(session, author),
        aliases=[a.normalized_name for a in author.aliases],
        recent_claims=[claim_out(c) for c in claims],
        recent_articles=[article_brief(a) for a in articles],
    )


@router.post("/{author_id}/aliases", response_model=AuthorDetail)
def create_alias(
    author_id: int, request: AliasRequest, session: Session = Depends(get_session)
) -> AuthorDetail:
    """Merge another byline spelling onto this author."""
    author = _get(session, author_id)
    normalized = normalize_name(request.name)
    if not normalized:
        raise HTTPException(status_code=422, detail="name did not normalize to anything")
    add_alias(session, author, normalized, request.outlet_domain)
    session.commit()
    return get_author(author_id, session)
