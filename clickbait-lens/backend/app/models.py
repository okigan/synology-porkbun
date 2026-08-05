"""Persistence model.

The shape mirrors the product question: *given a byline on a page, what has this
person claimed before, and how did those claims turn out?*
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ClaimKind(enum.StrEnum):
    """What sort of statement this is, which decides whether it is scoreable."""

    prediction = "prediction"  # falsifiable, about the future
    factual = "factual"  # checkable assertion about the present/past
    opinion = "opinion"  # not scoreable
    headline_promise = "headline_promise"  # the headline's implied payload


class Resolution(enum.StrEnum):
    unresolved = "unresolved"
    true = "true"
    mostly_true = "mostly_true"
    mixed = "mixed"
    mostly_false = "mostly_false"
    false = "false"
    unverifiable = "unverifiable"


#: Numeric outcome used by the Brier-style accuracy score. ``None`` means the
#: claim does not contribute to the author's track record.
RESOLUTION_OUTCOME: dict[Resolution, float | None] = {
    Resolution.unresolved: None,
    Resolution.unverifiable: None,
    Resolution.true: 1.0,
    Resolution.mostly_true: 0.75,
    Resolution.mixed: 0.5,
    Resolution.mostly_false: 0.25,
    Resolution.false: 0.0,
}


article_authors = Table(
    "article_authors",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)


class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))

    articles: Mapped[list[Article]] = relationship(back_populates="outlet")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Normalized identity key, e.g. ``"jane-q-smith"``. Unique per person, not
    #: per byline: aliases collapse onto this row.
    canonical_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    primary_outlet_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    aliases: Mapped[list[AuthorAlias]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    claims: Mapped[list[Claim]] = relationship(back_populates="author")
    articles: Mapped[list[Article]] = relationship(
        secondary=article_authors, back_populates="authors"
    )


class AuthorAlias(Base):
    """A byline spelling that maps to an author.

    ``outlet_domain`` is nullable: a global alias matches everywhere, an
    outlet-scoped one only disambiguates within that publication.
    """

    __tablename__ = "author_aliases"
    __table_args__ = (UniqueConstraint("normalized_name", "outlet_domain", name="uq_alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    outlet_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="seed")

    author: Mapped[Author] = relationship(back_populates="aliases")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    outlet_id: Mapped[int | None] = mapped_column(ForeignKey("outlets.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    clickbait_score: Mapped[float] = mapped_column(Float, default=0.0)
    signals: Mapped[list[dict]] = mapped_column(JSON, default=list)
    body_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    outlet: Mapped[Outlet | None] = relationship(back_populates="articles")
    authors: Mapped[list[Author]] = relationship(
        secondary=article_authors, back_populates="articles"
    )
    claims: Mapped[list[Claim]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=True
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id"), nullable=True)

    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[ClaimKind] = mapped_column(Enum(ClaimKind), default=ClaimKind.factual)
    #: How strongly it is asserted, 0 (heavily hedged) .. 1 (flat assertion).
    assertiveness: Mapped[float] = mapped_column(Float, default=0.5)
    #: Extractor's confidence that this really is a claim of the stated kind.
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    horizon_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resolution: Mapped[Resolution] = mapped_column(Enum(Resolution), default=Resolution.unresolved)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    article: Mapped[Article | None] = relationship(back_populates="claims")
    author: Mapped[Author | None] = relationship(back_populates="claims")
    verifications: Mapped[list[VerificationRun]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )

    @property
    def outcome(self) -> float | None:
        return RESOLUTION_OUTCOME[self.resolution]


class VerificationRun(Base):
    """One attempt at resolving a claim against live evidence."""

    __tablename__ = "verification_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    query: Mapped[str] = mapped_column(Text)
    suggested_resolution: Mapped[Resolution] = mapped_column(Enum(Resolution))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    claim: Mapped[Claim] = relationship(back_populates="verifications")
