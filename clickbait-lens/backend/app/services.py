"""Application services — the glue between the API layer and the domain modules."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis import PageContent, get_analyzer
from .analysis.clickbait import verdict_for
from .identity import resolve_authors
from .models import Article, Author, Claim, Outlet
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ArticleBrief,
    AuthorSummary,
    ClaimOut,
    SignalOut,
    TrustOut,
)
from .scoring import compute_trust

TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "cmpid")


def canonical_url(url: str) -> str:
    """Drop tracking parameters and fragments so the same article dedupes."""
    parsed = urlparse(url)
    query = "&".join(
        part
        for part in parsed.query.split("&")
        if part and not any(part.lower().startswith(p) for p in TRACKING_PARAMS)
    )
    return urlunparse(parsed._replace(query=query, fragment=""))


def domain_of(url: str) -> str | None:
    netloc = urlparse(url).netloc.lower().removeprefix("www.")
    return netloc or None


def get_or_create_outlet(session: Session, url: str, name: str | None) -> Outlet | None:
    domain = domain_of(url)
    if not domain:
        return None
    outlet = session.scalar(select(Outlet).where(Outlet.domain == domain))
    if outlet is None:
        outlet = Outlet(domain=domain, name=name or domain)
        session.add(outlet)
        session.flush()
    elif name and outlet.name == outlet.domain:
        outlet.name = name
    return outlet


def trust_for(session: Session, author: Author) -> TrustOut:
    claims = session.scalars(select(Claim).where(Claim.author_id == author.id)).all()
    report = compute_trust(list(claims), list(author.articles))
    return TrustOut(**report.to_dict())


def author_summary(session: Session, author: Author) -> AuthorSummary:
    return AuthorSummary(
        id=author.id,
        canonical_key=author.canonical_key,
        display_name=author.display_name,
        primary_outlet_domain=author.primary_outlet_domain,
        bio=author.bio,
        trust=trust_for(session, author),
    )


def claim_out(claim: Claim) -> ClaimOut:
    article = claim.article
    return ClaimOut(
        id=claim.id,
        text=claim.text,
        kind=claim.kind,
        assertiveness=round(claim.assertiveness, 3),
        extraction_confidence=round(claim.extraction_confidence, 3),
        horizon_text=claim.horizon_text,
        target_date=claim.target_date,
        resolution=claim.resolution,
        resolution_method=claim.resolution_method,
        resolution_notes=claim.resolution_notes,
        author_id=claim.author_id,
        article_url=article.url if article else None,
        article_title=article.title if article else None,
        published_at=article.published_at if article else None,
    )


def article_brief(article: Article) -> ArticleBrief:
    return ArticleBrief(
        id=article.id,
        url=article.url,
        title=article.title,
        clickbait_score=article.clickbait_score,
        published_at=article.published_at,
    )


def analyze_page(session: Session, request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a page and, unless told otherwise, record it against its authors."""
    url = canonical_url(request.url)
    page = PageContent(
        title=request.title.strip(),
        body=request.body or "",
        url=url,
        dek=request.dek or "",
    )
    reference = (request.published_at or datetime.now(UTC)).date()
    result = get_analyzer().analyze(page, reference=reference)

    outlet = get_or_create_outlet(session, url, request.outlet_name) if request.persist else None
    outlet_domain = domain_of(url)
    authors: list[Author] = []
    if request.byline:
        authors = resolve_authors(session, request.byline, outlet_domain, create=request.persist)

    article: Article | None = None
    if request.persist:
        article = session.scalar(select(Article).where(Article.url == url))
        if article is None:
            article = Article(url=url, title=page.title)
            session.add(article)
        article.title = page.title
        article.outlet_id = outlet.id if outlet else None
        article.published_at = request.published_at
        article.fetched_at = datetime.now(UTC)
        article.clickbait_score = result.clickbait_score
        article.signals = [s.to_dict() for s in result.signals]
        article.body_excerpt = page.body[:2000]
        article.authors = authors
        session.flush()

        # Re-extraction replaces machine-made claims but must not discard the
        # resolutions a human or a verification run has already recorded.
        keep = {c.text: c for c in article.claims if c.resolution.value != "unresolved"}
        for existing in list(article.claims):
            if existing.text not in keep:
                session.delete(existing)
        session.flush()

        for extracted in result.claims:
            if extracted.text in keep:
                continue
            session.add(
                Claim(
                    article_id=article.id,
                    author_id=authors[0].id if authors else None,
                    text=extracted.text,
                    kind=extracted.kind,
                    assertiveness=extracted.assertiveness,
                    extraction_confidence=extracted.extraction_confidence,
                    horizon_text=extracted.horizon_text,
                    target_date=extracted.target_date,
                )
            )
        session.commit()
        session.refresh(article)

    claims = (
        [claim_out(c) for c in article.claims]
        if article is not None
        else [
            ClaimOut(
                text=c.text,
                kind=c.kind,
                assertiveness=round(c.assertiveness, 3),
                extraction_confidence=round(c.extraction_confidence, 3),
                horizon_text=c.horizon_text,
                target_date=c.target_date,
            )
            for c in result.claims
        ]
    )
    claims.sort(key=lambda c: (c.kind != "prediction", -c.extraction_confidence))

    return AnalyzeResponse(
        url=url,
        title=page.title,
        outlet_domain=outlet_domain,
        outlet_name=outlet.name if outlet else request.outlet_name,
        analyzer=result.analyzer,
        clickbait_score=result.clickbait_score,
        verdict=verdict_for(result.clickbait_score),
        signals=[SignalOut(**s.to_dict()) for s in result.signals],
        claims=claims,
        authors=[author_summary(session, a) for a in authors],
        article_id=article.id if article else None,
    )
