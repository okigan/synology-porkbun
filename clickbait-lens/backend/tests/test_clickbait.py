from __future__ import annotations

from app.analysis.clickbait import PageContent, analyze_clickbait, verdict_for

CLEAN_BODY = (
    "The European Central Bank raised its deposit rate by 25 basis points on Thursday, "
    "taking it to 4 percent. Christine Lagarde said the governing council would keep "
    "rates restrictive for as long as necessary. Inflation in the euro area fell to 5.2 "
    "percent in August, down from 5.3 percent in July. Economists at Barclays expect one "
    "further increase before the end of the year. The bank also trimmed its growth "
    "forecast for 2024 to 1 percent."
)


def signal_ids(page: PageContent) -> set[str]:
    _, signals = analyze_clickbait(page)
    return {s.id for s in signals}


def test_straight_news_headline_scores_low():
    page = PageContent(title="ECB raises deposit rate to 4 percent", body=CLEAN_BODY)
    score, _ = analyze_clickbait(page)
    assert score < 25
    assert verdict_for(score) in {"clean", "low"}


def test_curiosity_gap_is_detected():
    page = PageContent(title="This is why the ECB decision will shock you", body=CLEAN_BODY)
    ids = signal_ids(page)
    assert "curiosity_gap" in ids
    assert "hype_lexicon" in ids


def test_headline_terms_absent_from_body():
    page = PageContent(
        title="Bitcoin whales stampede into Argentine farmland derivatives", body=CLEAN_BODY
    )
    score, signals = analyze_clickbait(page)
    ids = {s.id for s in signals}
    assert "headline_body_divergence" in ids
    assert score > 35


def test_assertive_headline_over_hedged_body():
    body = (
        "Analysts suggest the euro area may slip into recession next year. The bank's own "
        "staff projections indicate growth could stall, though officials cautioned the "
        "range is wide. Some economists argue a downturn is perhaps already under way. "
        "A recession in the euro area would probably be shallow, according to two of the "
        "forecasters surveyed."
    )
    page = PageContent(title="The euro area is heading into recession", body=body)
    ids = signal_ids(page)
    assert "assertive_headline_hedged_body" in ids


def test_attribution_stripped_from_headline():
    body = (
        "According to a report published by the lobby group, the tax will destroy 200,000 "
        "jobs. The group claims the modelling is conservative. Critics say the estimate "
        "assumes no behavioural response at all. A treasury spokesman said the report's "
        "job loss figures were not recognised by the department."
    )
    page = PageContent(title="New tax will destroy 200,000 jobs", body=body)
    signals = {s.id: s for _, s in [(0, s) for s in analyze_clickbait(page)[1]]}
    assert "attribution_stripped" in signals
    body_evidence = [e for e in signals["attribution_stripped"].evidence if e.where == "body"]
    assert body_evidence, "the extension needs a body sentence to highlight"


def test_unanswered_question_headline():
    page = PageContent(
        title="Is the housing market about to collapse?",
        body="Prices rose 2 percent last quarter. Mortgage approvals were flat.",
    )
    assert "unanswered_question" in signal_ids(page)


def test_signals_carry_highlightable_evidence():
    page = PageContent(title="You won't believe what the ECB did next", body=CLEAN_BODY)
    _, signals = analyze_clickbait(page)
    assert signals
    for signal in signals:
        assert signal.evidence, f"{signal.id} produced no evidence"
        assert all(e.where in {"headline", "body"} for e in signal.evidence)


def test_score_is_bounded():
    page = PageContent(
        title="SHOCKING!! 7 insane reasons you won't believe this is why experts say never",
        body="Short.",
    )
    score, _ = analyze_clickbait(page)
    assert 0 <= score <= 100
