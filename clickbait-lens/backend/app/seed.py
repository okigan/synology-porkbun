"""Demo data.

Enough of a track record that the trust index means something the first time
you open the extension: two authors with resolved predictions going opposite
ways, plus an alias so the cross-outlet merge is visible.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, Author, AuthorAlias, Claim, ClaimKind, Outlet, Resolution

OUTLETS = [
    ("economist.com", "The Economist"),
    ("ft.com", "Financial Times"),
    ("example-news.test", "Example News"),
]


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


SEED_AUTHORS: list[dict] = [
    {
        "key": "helena-marsh",
        "name": "Helena Marsh",
        "outlet": "economist.com",
        "bio": "Economics correspondent. Covers energy markets and monetary policy.",
        "aliases": [("h marsh", "economist.com"), ("helena b marsh", None)],
        "articles": [
            {
                "url": "https://www.economist.com/finance/2022/03/11/the-coming-energy-reckoning",
                "title": "The coming energy reckoning",
                "published": _dt(2022, 3, 11),
                "clickbait": 12.0,
                "claims": [
                    {
                        "text": (
                            "European gas prices will fall back below 50 euros per megawatt "
                            "hour by the end of 2023."
                        ),
                        "kind": ClaimKind.prediction,
                        "assertiveness": 0.9,
                        "target": _dt(2023, 12, 31),
                        "resolution": Resolution.true,
                        "notes": "TTF front-month settled near 32 EUR/MWh in December 2023.",
                    },
                    {
                        "text": (
                            "Germany is likely to avoid rationing industrial gas over the winter."
                        ),
                        "kind": ClaimKind.prediction,
                        "assertiveness": 0.55,
                        "target": _dt(2023, 3, 31),
                        "resolution": Resolution.true,
                        "notes": "No industrial rationing was imposed.",
                    },
                ],
            },
            {
                "url": "https://www.economist.com/finance/2023/06/02/the-rate-plateau",
                "title": "The rate plateau",
                "published": _dt(2023, 6, 2),
                "clickbait": 8.0,
                "claims": [
                    {
                        "text": (
                            "The European Central Bank will hold rates above 3 percent "
                            "through 2024."
                        ),
                        "kind": ClaimKind.prediction,
                        "assertiveness": 0.8,
                        "target": _dt(2024, 12, 31),
                        "resolution": Resolution.mostly_true,
                        "notes": "The deposit rate stayed at or above 3% for most of 2024.",
                    }
                ],
            },
        ],
    },
    {
        "key": "dane-corliss",
        "name": "Dane Corliss",
        "outlet": "example-news.test",
        "bio": "Technology columnist.",
        "aliases": [("d corliss", "example-news.test")],
        "articles": [
            {
                "url": "https://example-news.test/2021/tech/the-office-is-dead",
                "title": "The office is dead — and nobody is talking about it",
                "published": _dt(2021, 9, 14),
                "clickbait": 71.0,
                "claims": [
                    {
                        "text": (
                            "By 2024 more than half of all knowledge workers will never "
                            "return to a physical office."
                        ),
                        "kind": ClaimKind.prediction,
                        "assertiveness": 0.95,
                        "target": _dt(2024, 12, 31),
                        "resolution": Resolution.false,
                        "notes": "Hybrid attendance surveys put fully-remote well under half.",
                    },
                    {
                        "text": (
                            "Commercial office vacancy rates will exceed 40 percent in "
                            "major American cities by 2024."
                        ),
                        "kind": ClaimKind.prediction,
                        "assertiveness": 0.9,
                        "target": _dt(2024, 12, 31),
                        "resolution": Resolution.mostly_false,
                        "notes": "Peak big-city vacancy was closer to 20-25 percent.",
                    },
                ],
            },
            {
                "url": "https://example-news.test/2023/tech/every-company-will-be-an-ai-company",
                "title": "Every single company will be an AI company by next year",
                "published": _dt(2023, 2, 8),
                "clickbait": 64.0,
                "claims": [
                    {
                        "text": (
                            "Every major retailer will deploy generative AI in customer "
                            "service by 2024."
                        ),
                        "kind": ClaimKind.prediction,
                        "assertiveness": 0.95,
                        "target": _dt(2024, 12, 31),
                        "resolution": Resolution.mixed,
                        "notes": "Widely piloted, far from universal.",
                    }
                ],
            },
        ],
    },
]


def seed(session: Session) -> int:
    """Insert demo data if the database is empty. Returns authors created."""
    if session.scalar(select(Author).limit(1)) is not None:
        return 0

    outlets: dict[str, Outlet] = {}
    for domain, name in OUTLETS:
        outlet = Outlet(domain=domain, name=name)
        session.add(outlet)
        outlets[domain] = outlet
    session.flush()

    created = 0
    for spec in SEED_AUTHORS:
        author = Author(
            canonical_key=spec["key"],
            display_name=spec["name"],
            primary_outlet_domain=spec["outlet"],
            bio=spec["bio"],
        )
        author.aliases.append(
            AuthorAlias(
                normalized_name=spec["key"].replace("-", " "),
                outlet_domain=None,
                source="seed",
            )
        )
        for normalized, outlet_domain in spec["aliases"]:
            author.aliases.append(
                AuthorAlias(normalized_name=normalized, outlet_domain=outlet_domain, source="seed")
            )
        session.add(author)
        session.flush()
        created += 1

        for art in spec["articles"]:
            article = Article(
                url=art["url"],
                title=art["title"],
                outlet_id=outlets[spec["outlet"]].id,
                published_at=art["published"],
                clickbait_score=art["clickbait"],
                signals=[],
            )
            article.authors.append(author)
            session.add(article)
            session.flush()

            for c in art["claims"]:
                session.add(
                    Claim(
                        article_id=article.id,
                        author_id=author.id,
                        text=c["text"],
                        kind=c["kind"],
                        assertiveness=c["assertiveness"],
                        extraction_confidence=0.9,
                        target_date=c["target"],
                        resolution=c["resolution"],
                        resolved_at=datetime.now(UTC),
                        resolution_method="seed",
                        resolution_notes=c["notes"],
                    )
                )

    session.commit()
    return created
