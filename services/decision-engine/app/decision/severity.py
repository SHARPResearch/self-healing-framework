"""
Severity Calculator.

    EFFECTIVE_SEVERITY = BASE × CENTRALITY × BLAST_FACTOR

    BASE_SEVERITY from anomaly.severity label:
        "low"    → 0.3
        "medium" → 0.6
        "high"   → 0.9

    CENTRALITY from graph (already in [1.0, 2.0])
    BLAST_FACTOR from graph (already in [1.0, 1.5])

    Maximum = 0.9 × 2.0 × 1.5 = 2.7
    Normalized to [0, 1] by dividing by 2.7.
"""
from __future__ import annotations

from typing import Any

from app.decision.models import SeverityBreakdown

# Max possible value, used for normalization
_MAX_EFFECTIVE = 0.9 * 2.0 * 1.5  # = 2.7

# Label thresholds on the normalized score
_LABEL_THRESHOLDS = [
    (0.75, "CRITICAL"),
    (0.55, "HIGH"),
    (0.35, "MEDIUM"),
    (0.00, "LOW"),
]


def _base_from_label(severity: str | None) -> float:
    """Map a severity label to the numeric base weight."""
    if not severity:
        return 0.3
    s = str(severity).lower().strip()
    if s in ("high", "critical", "failing"):
        return 0.9
    if s in ("medium", "degraded", "warn", "warning"):
        return 0.6
    return 0.3


def _label_from_normalized(n: float) -> str:
    for threshold, label in _LABEL_THRESHOLDS:
        if n >= threshold:
            return label
    return "LOW"


def compute_severity(
    anomaly: dict[str, Any],
    centrality: float,
    blast_factor: float,
) -> SeverityBreakdown:
    """
    Compute the full severity breakdown for one anomaly.

    Args:
        anomaly       — the raw anomaly dict (must have 'severity')
        centrality    — from AnomalyContext (1.0 .. 2.0)
        blast_factor  — from AnomalyContext (1.0 .. 1.5)

    Returns:
        SeverityBreakdown with all four numbers + label
    """
    base = _base_from_label(anomaly.get("severity"))
    c = float(centrality)
    b = float(blast_factor)

    # Clamp to declared ranges — defensive
    c = max(1.0, min(2.0, c))
    b = max(1.0, min(1.5, b))

    effective = base * c * b
    normalized = min(1.0, effective / _MAX_EFFECTIVE)

    return SeverityBreakdown(
        base_severity=base,
        centrality=c,
        blast_factor=b,
        effective_severity=round(effective, 4),
        normalized=round(normalized, 4),
        label=_label_from_normalized(normalized),
    )