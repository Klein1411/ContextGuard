"""Public API for ContextGuard."""

from context_guard.core.guard import ContextGuard
from context_guard.schemas.models import (
    AnalyzeResult,
    Fact,
    GuardConfig,
    ProtectedSpan,
    RecommendedAction,
    RiskLevel,
    SafetyStatus,
    ValidationResult,
    Violation,
)

__version__ = "0.1.0"

__all__ = [
    "AnalyzeResult",
    "ContextGuard",
    "Fact",
    "GuardConfig",
    "ProtectedSpan",
    "RecommendedAction",
    "RiskLevel",
    "SafetyStatus",
    "ValidationResult",
    "Violation",
]
