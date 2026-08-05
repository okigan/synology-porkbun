from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import AnalyzeRequest, AnalyzeResponse
from ..services import analyze_page

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, session: Session = Depends(get_session)) -> AnalyzeResponse:
    """Analyze an article: clickbait signals, claims, and author track records.

    This is the endpoint the content script calls on every article page.
    """
    if not request.title.strip():
        raise HTTPException(status_code=422, detail="title is required")
    return analyze_page(session, request)
