from __future__ import annotations

from collections import Counter, defaultdict

from context_guard.schemas.models import Fact, GuardConfig, RiskLevel, Violation


def _severity_for(kind: str, config: GuardConfig) -> RiskLevel:
    if kind in {"version", "currency", "percentage", "code", "config", "boolean"}:
        return RiskLevel.CRITICAL
    if kind in {"date", "unit", "url", "email", "path", "filename", "flag_or_literal"}:
        return RiskLevel.HIGH
    if kind == "number":
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def exact_violations(
    original: list[Fact], candidate: list[Fact], config: GuardConfig
) -> list[Violation]:
    """Compare protected values conservatively, preserving multiplicity and category."""
    violations: list[Violation] = []
    originals = defaultdict(list)
    candidates = defaultdict(list)
    for fact in original:
        originals[fact.type].append(fact)
    for fact in candidate:
        candidates[fact.type].append(fact)
    for kind, source_facts in originals.items():
        target_facts = candidates.get(kind, [])
        source_values = [fact.normalized_value or fact.text.lower() for fact in source_facts]
        target_values = [fact.normalized_value or fact.text.lower() for fact in target_facts]
        target_counter = Counter(target_values)
        missing: list[Fact] = []
        for fact, value in zip(source_facts, source_values, strict=True):
            if target_counter[value]:
                target_counter[value] -= 1
            else:
                missing.append(fact)
        if not missing:
            continue
        unmatched_candidates = [
            fact
            for fact in target_facts
            if target_counter[fact.normalized_value or fact.text.lower()] > 0
        ]
        for index, fact in enumerate(missing):
            replacement = unmatched_candidates[index] if index < len(unmatched_candidates) else None
            changed = replacement is not None
            code = "FACT_CHANGED" if changed else "FACT_REMOVED"
            if kind == "version" and config.profile == "technical":
                code = "VERSION_CHANGED" if changed else "VERSION_REMOVED"
            elif kind == "currency":
                code = "MONEY_CHANGED" if changed else "MONEY_REMOVED"
            elif kind in {
                "number", "percentage", "unit", "date", "time",
                "filename", "config", "boolean",
            }:
                code = f"{kind.upper()}_CHANGED" if changed else f"{kind.upper()}_REMOVED"
            severity = _severity_for(kind, config)
            violations.append(
                Violation(
                    code=code,
                    severity=severity,
                    category="exact",
                    message=(
                        f"Candidate changed {kind} information."
                        if changed
                        else f"Candidate removed {kind} information."
                    ),
                    original_span=fact.text,
                    candidate_span=replacement.text if replacement else None,
                    evidence={
                        "type": kind,
                        "normalized_original": fact.normalized_value,
                        "normalized_candidate": replacement.normalized_value
                        if replacement
                        else None,
                    },
                    confidence=fact.confidence,
                )
            )
    return violations
