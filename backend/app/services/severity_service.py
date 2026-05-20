from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    NORMAL = "Normal"
    MINOR = "Minor"
    MAJOR = "Major"
    CRITICAL = "Critical"
    HUMAN_REVIEW = "Human Review Required"


# Score thresholds (anomaly score 0.0 – 1.0)
_THRESHOLDS = [
    (0.30, Severity.NORMAL,       False),
    (0.50, Severity.MINOR,        False),
    (0.70, Severity.MAJOR,        False),
    (0.85, Severity.CRITICAL,     True),
    (1.01, Severity.HUMAN_REVIEW, True),   # catch-all upper bound
]


def score_to_severity(score: float) -> tuple[Severity, bool]:
    """
    Map a normalised anomaly score (0–1) to a severity level and a
    human_review_required flag.

    Returns:
        (severity, human_review_required)
    """
    score = max(0.0, min(1.0, float(score)))   # clamp defensively
    for threshold, severity, review in _THRESHOLDS:
        if score < threshold:
            return severity, review
    return Severity.HUMAN_REVIEW, True


def severity_to_status(severity: Severity) -> str:
    """Return 'normal' or 'defective' based on severity level."""
    return "normal" if severity == Severity.NORMAL else "defective"
