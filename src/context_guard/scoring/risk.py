from __future__ import annotations

from context_guard.schemas.models import RiskLevel, Violation

_WEIGHTS = {
    RiskLevel.LOW: 0.15,
    RiskLevel.MEDIUM: 0.35,
    RiskLevel.HIGH: 0.70,
    RiskLevel.CRITICAL: 0.98,
}


def risk_score(violations: list[Violation]) -> float:
    if not violations:
        return 0.0
    remaining = 1.0
    for violation in violations:
        remaining *= 1.0 - (_WEIGHTS[violation.severity] * violation.confidence)
    return round(min(1.0, 1.0 - remaining), 6)


def risk_level(score: float, violations: list[Violation]) -> RiskLevel:
    if any(v.severity is RiskLevel.CRITICAL for v in violations) or score >= 0.9:
        return RiskLevel.CRITICAL
    if score >= 0.6:
        return RiskLevel.HIGH
    if score >= 0.25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
