from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .models import ClaimKind, Resolution


class EvidenceOut(BaseModel):
    text: str
    where: str
    note: str = ""


class SignalOut(BaseModel):
    id: str
    label: str
    severity: float
    weight: float
    explanation: str
    evidence: list[EvidenceOut] = []


class ClaimOut(BaseModel):
    id: int | None = None
    text: str
    kind: ClaimKind
    assertiveness: float
    extraction_confidence: float
    horizon_text: str | None = None
    target_date: datetime | None = None
    resolution: Resolution = Resolution.unresolved
    resolution_method: str | None = None
    resolution_notes: str | None = None
    author_id: int | None = None
    article_url: str | None = None
    article_title: str | None = None
    published_at: datetime | None = None


class TrustOut(BaseModel):
    trust_index: float
    grade: str
    resolved_claims: int
    total_claims: int
    raw_accuracy: float | None
    adjusted_accuracy: float
    overconfidence: float
    mean_clickbait: float
    articles: int
    notes: list[str] = []
    breakdown: dict[str, float] = {}


class AuthorSummary(BaseModel):
    id: int
    canonical_key: str
    display_name: str
    primary_outlet_domain: str | None = None
    bio: str | None = None
    trust: TrustOut


class AuthorDetail(AuthorSummary):
    aliases: list[str] = []
    recent_claims: list[ClaimOut] = []
    recent_articles: list[ArticleBrief] = []


class ArticleBrief(BaseModel):
    id: int
    url: str
    title: str
    clickbait_score: float
    published_at: datetime | None = None


class AnalyzeRequest(BaseModel):
    url: str
    title: str
    body: str = Field(default="", description="Extracted article text.")
    byline: str | None = None
    dek: str | None = None
    published_at: datetime | None = None
    outlet_name: str | None = None
    persist: bool = True


class AnalyzeResponse(BaseModel):
    url: str
    title: str
    outlet_domain: str | None = None
    outlet_name: str | None = None
    analyzer: str
    clickbait_score: float
    verdict: str
    signals: list[SignalOut]
    claims: list[ClaimOut]
    authors: list[AuthorSummary]
    article_id: int | None = None


class VerifyRequest(BaseModel):
    provider: str | None = Field(
        default=None, description="Override the configured search provider."
    )
    apply: bool = Field(
        default=False,
        description="Write the suggested resolution back onto the claim.",
    )


class SearchResultOut(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = ""
    published: str | None = None
    stance: float = 0.0
    stance_reason: str = ""


class VerifyResponse(BaseModel):
    claim_id: int
    claim_text: str
    query: str
    provider: str
    suggested_resolution: Resolution
    confidence: float
    rationale: str
    applied: bool
    evidence: list[SearchResultOut]
    search_url: str


class ResolutionRequest(BaseModel):
    resolution: Resolution
    notes: str | None = None


class AliasRequest(BaseModel):
    name: str
    outlet_domain: str | None = None


AuthorDetail.model_rebuild()
