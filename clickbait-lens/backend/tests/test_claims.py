from __future__ import annotations

from datetime import date

from app.analysis.claims import classify, extract_claims, parse_horizon
from app.models import ClaimKind

REF = date(2024, 6, 1)


def test_prediction_with_year_horizon():
    claim = classify("Global electric vehicle sales will exceed 30 million units by 2030.", REF)
    assert claim is not None
    assert claim.kind is ClaimKind.prediction
    assert claim.target_date.year == 2030
    assert claim.assertiveness > 0.8


def test_hedged_prediction_has_lower_assertiveness():
    firm = classify("Inflation will fall below 2 percent next year.", REF)
    hedged = classify(
        "Inflation may possibly fall below 2 percent next year, some economists suggest.", REF
    )
    assert firm is not None and hedged is not None
    assert hedged.assertiveness < firm.assertiveness


def test_reported_prediction_is_not_the_authors_own():
    claim = classify("The bank had predicted that rates would peak in March.", REF)
    assert claim is None or claim.kind is not ClaimKind.prediction


def test_opinion_is_classified_separately():
    claim = classify("I think the whole policy is frankly outrageous and misguided.", REF)
    assert claim is not None
    assert claim.kind is ClaimKind.opinion


def test_quantified_statement_is_factual():
    claim = classify("Unemployment stood at 4.2 percent in April, the agency reported.", REF)
    assert claim is not None
    assert claim.kind is ClaimKind.factual


def test_relative_horizons():
    assert parse_horizon("within five years the grid will be clean", REF)[1].year == 2029
    assert parse_horizon("over the next two years", REF)[1].year == 2026
    assert parse_horizon("next year", REF)[1].year == 2025
    assert parse_horizon("by the end of this decade", REF)[1].year == 2029


def test_headline_prediction_extracted_first():
    claims = extract_claims(
        body=(
            "The company shipped 1.2 million units last quarter. Analysts expect the "
            "figure to double by 2027. Management declined to comment."
        ),
        title="Acme will double shipments by 2027",
        reference=REF,
    )
    assert claims[0].kind is ClaimKind.headline_promise
    assert any(c.kind is ClaimKind.prediction for c in claims)


def test_short_and_giant_sentences_are_skipped():
    assert classify("It will.", REF) is None
    assert classify("will " * 200, REF) is None
