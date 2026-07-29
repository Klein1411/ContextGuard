from __future__ import annotations

import re

from context_guard.schemas.models import GuardConfig, RiskLevel, Violation

_NEGATION = {
    "vi": re.compile(r"\b(?:không|chưa|không được|không cần|không bao giờ)\b", re.I),
    "en": re.compile(r"\b(?:not|no|never|must not|do not|cannot)\b", re.I),
}
_CONDITION = {
    "vi": re.compile(r"\b(?:nếu|chỉ khi|miễn là|với điều kiện)\b", re.I),
    "en": re.compile(r"\b(?:if|only if|provided that|as long as)\b", re.I),
}
_EXCEPTION = {
    "vi": re.compile(r"\b(?:trừ khi|ngoại trừ)\b", re.I),
    "en": re.compile(r"\b(?:unless|except|except when)\b", re.I),
}
_MODALITY = {
    "vi": re.compile(r"\b(?:phải|nên|có thể|không được)\b", re.I),
    "en": re.compile(r"\b(?:must|should|may|must not)\b", re.I),
}
_COMPARISON = re.compile(
    r"(?:>=|<=|>|<|=|\bat least\b|\bat most\b|\bno more than\b|"
    r"\bno less than\b|\bgreater than\b|\bless than\b|\bí?t nhất\b|"
    r"\btối thiểu\b|\bkhông thấp hơn\b|\bkhông quá\b|\btối đa\b|"
    r"\bnhỏ hơn\b|\blớn hơn\b)",
    re.I,
)


def _marker(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def _marker_any(patterns: list[re.Pattern[str]], text: str) -> str | None:
    matches = [match for pattern in patterns if (match := pattern.search(text))]
    if not matches:
        return None
    return min(matches, key=lambda match: match.start()).group(0)


def logic_violations(
    original_text: str, candidate_text: str, language: str, config: GuardConfig
) -> list[Violation]:
    violations: list[Violation] = []
    lang = language if language in {"vi", "en"} else "en"

    def patterns(table: dict[str, re.Pattern[str]]) -> list[re.Pattern[str]]:
        return [table[lang], table["en" if lang == "vi" else "vi"]]

    original_neg = _marker_any(patterns(_NEGATION), original_text)
    candidate_neg = _marker_any(patterns(_NEGATION), candidate_text)
    if original_neg and not candidate_neg:
        violations.append(
            Violation(
                code="NEGATION_REMOVED",
                severity=RiskLevel.CRITICAL,
                category="logic",
                message="Candidate removed a required negation.",
                original_span=original_neg,
                evidence={"language": lang},
                confidence=0.98,
            )
        )
    elif original_neg and candidate_neg and original_neg.lower() != candidate_neg.lower():
        violations.append(
            Violation(
                code="NEGATION_CHANGED",
                severity=RiskLevel.CRITICAL,
                category="logic",
                message="Candidate changed the negation expression.",
                original_span=original_neg,
                candidate_span=candidate_neg,
                confidence=0.9,
            )
        )
    elif candidate_neg and not original_neg:
        violations.append(
            Violation(
                code="NEGATION_ADDED",
                severity=RiskLevel.CRITICAL,
                category="logic",
                message="Candidate introduced a negation absent from the original.",
                candidate_span=candidate_neg,
                confidence=0.95,
            )
        )

    original_cmp = _marker(_COMPARISON, original_text)
    candidate_cmp = _marker(_COMPARISON, candidate_text)
    if original_cmp and not candidate_cmp:
        violations.append(
            Violation(
                code="COMPARISON_REMOVED",
                severity=RiskLevel.CRITICAL,
                category="logic",
                message="Candidate removed a comparison or threshold.",
                original_span=original_cmp,
                confidence=0.95,
            )
        )
    elif original_cmp and candidate_cmp and original_cmp.lower() != candidate_cmp.lower():
        violations.append(
            Violation(
                code="COMPARISON_CHANGED",
                severity=RiskLevel.CRITICAL,
                category="logic",
                message="Candidate changed a comparison or threshold.",
                original_span=original_cmp,
                candidate_span=candidate_cmp,
                confidence=0.96,
            )
        )

    for code, pattern, label in (
        ("CONDITION_REMOVED", _CONDITION[lang], "condition"),
        ("EXCEPTION_REMOVED", _EXCEPTION[lang], "exception"),
    ):
        source = _marker_any(patterns({"vi": pattern, "en": pattern}), original_text)
        target = _marker_any(patterns({"vi": pattern, "en": pattern}), candidate_text)
        if source and not target:
            violations.append(
                Violation(
                    code=code,
                    severity=RiskLevel.CRITICAL,
                    category="logic",
                    message=f"Candidate removed a required {label}.",
                    original_span=source,
                    confidence=0.95,
                )
            )

    source_mod = _marker_any(patterns(_MODALITY), original_text)
    target_mod = _marker_any(patterns(_MODALITY), candidate_text)
    if source_mod and target_mod and source_mod.lower() != target_mod.lower():
        critical = {"must", "must not", "phải", "không được"}
        severity = (
            RiskLevel.CRITICAL
            if source_mod.lower() in critical or target_mod.lower() in critical
            else RiskLevel.HIGH
        )
        violations.append(
            Violation(
                code="MODALITY_CHANGED",
                severity=severity,
                category="logic",
                message="Candidate changed the obligation level.",
                original_span=source_mod,
                candidate_span=target_mod,
                confidence=0.92,
            )
        )
    elif source_mod and not target_mod:
        violations.append(
            Violation(
                code="MODALITY_REMOVED",
                severity=RiskLevel.HIGH,
                category="logic",
                message="Candidate removed an obligation or permission marker.",
                original_span=source_mod,
                confidence=0.9,
            )
        )
    return violations
