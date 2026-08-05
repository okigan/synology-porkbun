from __future__ import annotations

from app.models import Article, Claim, ClaimKind, Resolution
from app.scoring import compute_trust


def claim(resolution: Resolution, assertiveness: float = 0.9) -> Claim:
    return Claim(
        text="x",
        kind=ClaimKind.prediction,
        assertiveness=assertiveness,
        extraction_confidence=0.9,
        resolution=resolution,
    )


def article(score: float) -> Article:
    return Article(url=f"https://x/{score}", title="t", clickbait_score=score)


def test_no_history_is_unrated_not_zero():
    report = compute_trust([], [])
    assert report.grade == "unrated"
    assert report.resolved_claims == 0
    assert 40 <= report.trust_index <= 75


def test_accurate_author_outranks_inaccurate_one():
    good = compute_trust([claim(Resolution.true) for _ in range(10)], [article(10)])
    bad = compute_trust([claim(Resolution.false) for _ in range(10)], [article(70)])
    assert good.trust_index > bad.trust_index
    assert good.grade in {"strong", "good"}
    assert bad.grade in {"weak", "poor"}


def test_small_sample_is_pulled_toward_neutral():
    one = compute_trust([claim(Resolution.true)], [])
    many = compute_trust([claim(Resolution.true) for _ in range(20)], [])
    assert one.adjusted_accuracy < many.adjusted_accuracy
    assert any("pulled toward neutral" in n for n in one.notes)


def test_overconfidence_is_measured():
    report = compute_trust([claim(Resolution.false, assertiveness=0.95) for _ in range(6)], [])
    assert report.overconfidence > 0.5
    assert any("more firmly" in n for n in report.notes)


def test_hedged_but_wrong_is_penalised_less_than_confident_and_wrong():
    hedged = compute_trust([claim(Resolution.false, 0.4) for _ in range(6)], [])
    confident = compute_trust([claim(Resolution.false, 0.95) for _ in range(6)], [])
    assert hedged.trust_index > confident.trust_index


def test_unresolved_claims_do_not_count():
    report = compute_trust([claim(Resolution.unresolved) for _ in range(5)], [])
    assert report.resolved_claims == 0
    assert report.total_claims == 5
    assert report.raw_accuracy is None


def test_clickbait_history_drags_the_index_down():
    clean = compute_trust([claim(Resolution.true) for _ in range(8)], [article(5)])
    baity = compute_trust([claim(Resolution.true) for _ in range(8)], [article(85)])
    assert clean.trust_index > baity.trust_index
    assert any("clickbait" in n for n in baity.notes)
