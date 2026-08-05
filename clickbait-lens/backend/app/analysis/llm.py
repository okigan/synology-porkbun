"""Optional LLM-backed analyzer.

This is **not** the default. The product goal is an LLM-free detector, so the
heuristic analyzer is the reference implementation and this adapter exists to
benchmark it — turn it on with ``CBL_ANALYZER=llm`` while the rule set matures.

Requires the ``llm`` extra (``uv sync --extra llm``) and ``CBL_ANTHROPIC_API_KEY``
(or ``ANTHROPIC_API_KEY`` in the environment).
"""

from __future__ import annotations

import json
import logging
from datetime import date

from ..config import get_settings
from ..models import ClaimKind
from .base import AnalysisResult
from .claims import ExtractedClaim, parse_horizon
from .clickbait import Evidence, PageContent, Signal, analyze_clickbait
from .heuristic import HeuristicAnalyzer
from .text import clamp

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You audit news articles for headline integrity.

Given a headline and article body, do two things:

1. Identify where the headline overstates, distorts, or fails to deliver what
   the body supports. Quote the exact body sentence for each finding.
2. Extract the falsifiable claims the author makes, especially predictions
   about the future.

Be conservative: only report a mismatch you can point to a body sentence for.
Report every claim you find, including low-confidence ones — a separate step
filters them."""

#: Structured output schema. Mirrors the heuristic analyzer's shapes so both
#: backends are interchangeable behind the Analyzer protocol.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "clickbait_score": {
            "type": "integer",
            "description": "0-100, how much the headline oversells the article.",
        },
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "enum": [
                            "curiosity_gap",
                            "hype_lexicon",
                            "unanswered_question",
                            "absolutes",
                            "vague_authority",
                            "headline_body_divergence",
                            "assertive_headline_hedged_body",
                            "attribution_stripped",
                        ],
                    },
                    "label": {"type": "string"},
                    "severity": {"type": "number"},
                    "explanation": {"type": "string"},
                    "headline_fragment": {"type": "string"},
                    "body_sentence": {
                        "type": "string",
                        "description": "Verbatim sentence from the body, or empty.",
                    },
                },
                "required": [
                    "id",
                    "label",
                    "severity",
                    "explanation",
                    "headline_fragment",
                    "body_sentence",
                ],
                "additionalProperties": False,
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Verbatim sentence."},
                    "kind": {
                        "type": "string",
                        "enum": ["prediction", "factual", "opinion", "headline_promise"],
                    },
                    "assertiveness": {"type": "number"},
                    "confidence": {"type": "number"},
                    "horizon_text": {"type": "string"},
                },
                "required": ["text", "kind", "assertiveness", "confidence", "horizon_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["clickbait_score", "signals", "claims"],
    "additionalProperties": False,
}


class LLMAnalyzer:
    """Claude-backed analyzer. Falls back to heuristics if the call fails."""

    name = "llm"

    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "The 'llm' analyzer needs the optional dependency: uv sync --extra llm"
            ) from exc

        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model
        self._fallback = HeuristicAnalyzer()

    def analyze(self, page: PageContent, reference: date | None = None) -> AnalysisResult:
        try:
            payload = self._call(page)
        except Exception:  # pragma: no cover - network path
            log.exception("LLM analysis failed; falling back to heuristics")
            result = self._fallback.analyze(page, reference)
            result.analyzer = "heuristic (llm fallback)"
            return result
        return self._to_result(payload, page, reference)

    def _call(self, page: PageContent) -> dict:
        body = page.body[:40_000]
        response = self._client.messages.create(
            model=self._model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"URL: {page.url}\nHEADLINE: {page.title}\nDEK: {page.dek}\n\nBODY:\n{body}"
                    ),
                }
            ],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined to analyze this page")
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)

    def _to_result(
        self, payload: dict, page: PageContent, reference: date | None
    ) -> AnalysisResult:
        signals: list[Signal] = []
        for raw in payload.get("signals", []):
            evidence = [Evidence(text=raw["headline_fragment"], where="headline")]
            if raw.get("body_sentence"):
                evidence.append(
                    Evidence(text=raw["body_sentence"], where="body", note="contradicts headline")
                )
            signals.append(
                Signal(
                    id=raw["id"],
                    label=raw["label"],
                    severity=clamp(float(raw["severity"])),
                    weight=1.0,
                    explanation=raw["explanation"],
                    evidence=evidence,
                )
            )

        claims: list[ExtractedClaim] = []
        for raw in payload.get("claims", []):
            horizon_text = raw.get("horizon_text") or None
            _, target_date = parse_horizon(horizon_text or raw["text"], reference)
            claims.append(
                ExtractedClaim(
                    text=raw["text"],
                    kind=ClaimKind(raw["kind"]),
                    assertiveness=clamp(float(raw["assertiveness"])),
                    extraction_confidence=clamp(float(raw["confidence"])),
                    horizon_text=horizon_text,
                    target_date=target_date,
                    cues=["llm"],
                )
            )

        # Keep the deterministic score alongside the model's, and take the higher
        # of the two so a rule the model missed still surfaces.
        heuristic_score, _ = analyze_clickbait(page)
        score = max(float(payload.get("clickbait_score", 0)), heuristic_score)
        return AnalysisResult(
            clickbait_score=round(score, 1), signals=signals, claims=claims, analyzer=self.name
        )
