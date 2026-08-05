"""Author prediction-accuracy and trust index.

The headline number is a 0-100 trust index, but the components matter more than
the composite — the API returns all of them so the extension can show *why* an
author scores the way they do, and so a low score from three resolved claims
never looks like a low score from three hundred.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..analysis.text import clamp
from ..models import Article, Claim, ClaimKind

#: Pseudo-count pulling a thin track record toward the neutral prior. With
#: PRIOR_STRENGTH=5, one correct prediction gives 0.58, not 1.0.
PRIOR_STRENGTH = 5.0
PRIOR_ACCURACY = 0.5

WEIGHT_ACCURACY = 0.6
WEIGHT_CLICKBAIT = 0.2
WEIGHT_CALIBRATION = 0.2


@dataclass
class TrustReport:
    trust_index: float  # 0-100
    grade: str
    resolved_claims: int
    total_claims: int
    #: 1 - Brier score over resolved claims; None when nothing is resolved.
    raw_accuracy: float | None
    #: Accuracy shrunk toward the prior to account for sample size.
    adjusted_accuracy: float
    #: Positive means the author asserts more confidently than outcomes justify.
    overconfidence: float
    mean_clickbait: float
    articles: int
    #: Human-readable notes explaining the number.
    notes: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _grade(index: float, resolved: int) -> str:
    if resolved == 0:
        return "unrated"
    if index >= 80:
        return "strong"
    if index >= 62:
        return "good"
    if index >= 45:
        return "mixed"
    if index >= 28:
        return "weak"
    return "poor"


def compute_trust(claims: list[Claim], articles: list[Article]) -> TrustReport:
    """Score an author from their claims and articles."""
    scoreable = [c for c in claims if c.kind != ClaimKind.opinion]
    resolved = [c for c in scoreable if c.outcome is not None]

    notes: list[str] = []

    if resolved:
        # Brier score: mean squared distance between how firmly the claim was
        # asserted and how it actually turned out.
        brier = sum((c.assertiveness - c.outcome) ** 2 for c in resolved) / len(resolved)
        raw_accuracy: float | None = clamp(1.0 - brier)
        mean_assertiveness = sum(c.assertiveness for c in resolved) / len(resolved)
        mean_outcome = sum(c.outcome for c in resolved) / len(resolved)
        overconfidence = round(mean_assertiveness - mean_outcome, 3)
    else:
        raw_accuracy = None
        overconfidence = 0.0
        notes.append("No resolved predictions yet — accuracy is the neutral prior.")

    base = raw_accuracy if raw_accuracy is not None else PRIOR_ACCURACY
    n = len(resolved)
    adjusted_accuracy = (n * base + PRIOR_STRENGTH * PRIOR_ACCURACY) / (n + PRIOR_STRENGTH)

    if articles:
        mean_clickbait = sum(a.clickbait_score for a in articles) / len(articles)
    else:
        mean_clickbait = 0.0

    clickbait_component = clamp(1.0 - mean_clickbait / 100)
    calibration_component = clamp(1.0 - abs(overconfidence))

    index = 100 * (
        WEIGHT_ACCURACY * adjusted_accuracy
        + WEIGHT_CLICKBAIT * clickbait_component
        + WEIGHT_CALIBRATION * calibration_component
    )

    if n and n < 5:
        notes.append(f"Only {n} resolved claim(s); the score is pulled toward neutral.")
    if overconfidence > 0.2:
        notes.append("States claims more firmly than outcomes have justified.")
    elif overconfidence < -0.2:
        notes.append("Hedges more than outcomes have warranted.")
    if mean_clickbait >= 50:
        notes.append(f"Headlines average {mean_clickbait:.0f}/100 on clickbait signals.")

    return TrustReport(
        trust_index=round(index, 1),
        grade=_grade(index, n),
        resolved_claims=n,
        total_claims=len(scoreable),
        raw_accuracy=round(raw_accuracy, 3) if raw_accuracy is not None else None,
        adjusted_accuracy=round(adjusted_accuracy, 3),
        overconfidence=overconfidence,
        mean_clickbait=round(mean_clickbait, 1),
        articles=len(articles),
        notes=notes,
        breakdown={
            "accuracy": round(WEIGHT_ACCURACY * adjusted_accuracy * 100, 1),
            "headline_integrity": round(WEIGHT_CLICKBAIT * clickbait_component * 100, 1),
            "calibration": round(WEIGHT_CALIBRATION * calibration_component * 100, 1),
        },
    )
