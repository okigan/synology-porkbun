from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models import Claim, ClaimKind, Resolution
from app.verification.base import SearchResult
from app.verification.providers import DuckDuckGoProvider, FixtureProvider
from app.verification.verifier import aggregate, build_query, score_stance, verify_claim


def make_claim(text: str, target: datetime | None = None) -> Claim:
    return Claim(
        text=text,
        kind=ClaimKind.prediction,
        assertiveness=0.9,
        extraction_confidence=0.8,
        target_date=target,
    )


def test_query_drops_prediction_verbs_and_adds_the_year():
    claim = make_claim(
        "European gas prices will fall below 50 euros per megawatt hour.",
        datetime(2023, 12, 31, tzinfo=UTC),
    )
    query = build_query(claim)
    assert "will" not in query.split()
    assert "2023" in query
    assert "gas" in query


def test_stance_detects_refutation():
    claim = "More than half of knowledge workers will never return to a physical office."
    result = SearchResult(
        title="Hybrid work settles in",
        url="https://apnews.com/x",
        snippet=(
            "Predictions that most knowledge workers would never return to an office "
            "failed to materialize; fully remote work stayed a minority."
        ),
        source="apnews.com",
    )
    stance, reason, relevance = score_stance(claim, result)
    assert stance < -0.3
    assert relevance > 0.15
    assert "refutes" in reason


def test_stance_detects_support():
    claim = "European gas prices will fall below 50 euros per megawatt hour."
    result = SearchResult(
        title="Gas ends the year at 32 euros",
        url="https://reuters.com/x",
        snippet=(
            "Dutch TTF gas prices settled near 32 euros per megawatt hour, "
            "confirmed by exchange data."
        ),
        source="reuters.com",
    )
    stance, _, _ = score_stance(claim, result)
    assert stance > 0.2


def test_unrelated_result_is_ignored():
    stance, reason, relevance = score_stance(
        "European gas prices will fall below 50 euros per megawatt hour.",
        SearchResult(
            title="Best pasta recipes",
            url="https://example.com/pasta",
            snippet="Twelve ways with tomatoes and basil.",
            source="example.com",
        ),
    )
    assert stance == 0.0
    assert relevance < 0.15
    assert reason == "not topically related"


def test_numeric_threshold_shortfall_refutes():
    claim = "Office vacancy rates will exceed 40 percent by 2024."
    result = SearchResult(
        title="US office vacancy hits record 20.4 percent",
        url="https://reuters.com/y",
        snippet="National office vacancy reached a record 20.4 percent in 2024.",
        source="reuters.com",
    )
    stance, reason, _ = score_stance(claim, result)
    assert stance < 0
    assert "falls short" in reason


def test_aggregate_weights_disagreement_down():
    supporting = SearchResult(title="a", url="u", snippet="s", source="reuters.com", stance=0.8)
    refuting = SearchResult(title="b", url="u", snippet="s", source="reuters.com", stance=-0.8)
    _, split_confidence, _ = aggregate([supporting, refuting])
    _, agreed_confidence, _ = aggregate([supporting, supporting])
    assert split_confidence < agreed_confidence


def test_aggregate_with_no_signal_stays_unresolved():
    resolution, confidence, _ = aggregate(
        [SearchResult(title="a", url="u", snippet="s", stance=0.0)]
    )
    assert resolution is Resolution.unresolved
    assert confidence < 0.3


@pytest.mark.asyncio
async def test_end_to_end_verification_against_fixtures():
    claim = make_claim(
        "By 2024 more than half of all knowledge workers will never return to a physical office.",
        datetime(2024, 12, 31, tzinfo=UTC),
    )
    outcome = await verify_claim(claim, provider=FixtureProvider())
    assert outcome.provider == "fixture"
    assert outcome.suggested_resolution in {
        Resolution.false.value,
        Resolution.mostly_false.value,
    }
    assert outcome.evidence
    assert all(e.stance_reason for e in outcome.evidence)


@pytest.mark.asyncio
async def test_no_results_reports_unverifiable():
    class Empty:
        name = "empty"

        async def search(self, query: str, limit: int = 8):
            return []

    outcome = await verify_claim(make_claim("Nothing at all will happen ever."), provider=Empty())
    assert outcome.suggested_resolution == Resolution.unverifiable.value
    assert outcome.confidence == 0.0


def test_duckduckgo_html_parsing():
    html = """
    <div class="result">
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Freuters.com%2Fstory">Gas falls</a>
      <a class="result__snippet">Prices settled near 32 euros.</a>
    </div>
    """
    results = DuckDuckGoProvider()._parse(html, limit=5)
    assert len(results) == 1
    assert results[0].url == "https://reuters.com/story"
    assert results[0].source == "reuters.com"
    assert "32 euros" in results[0].snippet
