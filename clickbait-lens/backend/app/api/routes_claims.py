from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Claim, ClaimKind, Resolution, VerificationRun
from ..schemas import ClaimOut, ResolutionRequest, VerifyRequest, VerifyResponse
from ..services import claim_out
from ..verification import get_provider, search_url, verify_claim

router = APIRouter(prefix="/claims", tags=["claims"])


def _get(session: Session, claim_id: int) -> Claim:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return claim


@router.get("", response_model=list[ClaimOut])
def list_claims(
    session: Session = Depends(get_session),
    author_id: int | None = None,
    kind: ClaimKind | None = None,
    resolution: Resolution | None = None,
    limit: int = Query(default=50, le=200),
) -> list[ClaimOut]:
    stmt = select(Claim).order_by(Claim.created_at.desc())
    if author_id is not None:
        stmt = stmt.where(Claim.author_id == author_id)
    if kind is not None:
        stmt = stmt.where(Claim.kind == kind)
    if resolution is not None:
        stmt = stmt.where(Claim.resolution == resolution)
    return [claim_out(c) for c in session.scalars(stmt.limit(limit)).all()]


@router.post("/{claim_id}/verify", response_model=VerifyResponse)
async def verify(
    claim_id: int,
    request: VerifyRequest | None = None,
    session: Session = Depends(get_session),
) -> VerifyResponse:
    """Search the live web for evidence about this claim and suggest a verdict.

    The verdict is a suggestion by default; pass ``apply: true`` to write it onto
    the claim, or use the resolution endpoint to set it by hand.
    """
    request = request or VerifyRequest()
    claim = _get(session, claim_id)
    provider = get_provider(request.provider) if request.provider else None
    author_name = claim.author.display_name if claim.author else None

    outcome = await verify_claim(claim, provider=provider, author_name=author_name)

    session.add(
        VerificationRun(
            claim_id=claim.id,
            provider=outcome.provider,
            query=outcome.query,
            suggested_resolution=Resolution(outcome.suggested_resolution),
            confidence=outcome.confidence,
            evidence=[e.to_dict() for e in outcome.evidence],
        )
    )

    applied = False
    if request.apply and outcome.suggested_resolution != Resolution.unresolved.value:
        claim.resolution = Resolution(outcome.suggested_resolution)
        claim.resolved_at = datetime.now(UTC)
        claim.resolution_method = f"auto:{outcome.provider}"
        claim.resolution_notes = outcome.rationale
        applied = True
    session.commit()

    return VerifyResponse(
        claim_id=claim.id,
        claim_text=claim.text,
        query=outcome.query,
        provider=outcome.provider,
        suggested_resolution=Resolution(outcome.suggested_resolution),
        confidence=outcome.confidence,
        rationale=outcome.rationale,
        applied=applied,
        evidence=[e.to_dict() for e in outcome.evidence],
        search_url=search_url(outcome.query),
    )


@router.post("/{claim_id}/resolution", response_model=ClaimOut)
def set_resolution(
    claim_id: int, request: ResolutionRequest, session: Session = Depends(get_session)
) -> ClaimOut:
    """Record a human verdict, overriding whatever verification suggested."""
    claim = _get(session, claim_id)
    claim.resolution = request.resolution
    claim.resolved_at = datetime.now(UTC)
    claim.resolution_method = "manual"
    claim.resolution_notes = request.notes
    session.commit()
    session.refresh(claim)
    return claim_out(claim)
