from __future__ import annotations

from context_guard.schemas.models import RecommendedAction, RiskLevel, SafetyStatus, Violation


def status_for(violations: list[Violation], warnings: list[str], policy: str) -> SafetyStatus:
    if any(v.severity is RiskLevel.CRITICAL for v in violations):
        return SafetyStatus.FAIL
    if violations:
        if policy == "lenient" and all(v.severity is RiskLevel.LOW for v in violations):
            return SafetyStatus.PASS
        return SafetyStatus.FAIL
    return SafetyStatus.UNCERTAIN if warnings else SafetyStatus.PASS


def action_for(status: SafetyStatus, policy: str, violations: list[Violation]) -> RecommendedAction:
    if status is SafetyStatus.PASS:
        return RecommendedAction.ACCEPT_CANDIDATE
    if status is SafetyStatus.FAIL:
        if any(
            v.code
            in {
                "NEGATION_REMOVED",
                "NEGATION_CHANGED",
                "COMPARISON_CHANGED",
                "CONDITION_REMOVED",
                "EXCEPTION_REMOVED",
            }
            for v in violations
        ):
            return RecommendedAction.USE_ORIGINAL
        return (
            RecommendedAction.RETRY_WITH_LOWER_COMPRESSION
            if policy == "lenient"
            else RecommendedAction.USE_ORIGINAL
        )
    return RecommendedAction.USE_ORIGINAL if policy == "strict" else RecommendedAction.MANUAL_REVIEW
