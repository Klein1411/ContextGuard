from __future__ import annotations

from context_guard.extraction.relations import extract_relations
from context_guard.schemas.models import GuardConfig, RiskLevel, Violation


def relation_violations(
    original_text: str, candidate_text: str, language: str, config: GuardConfig
) -> list[Violation]:
    del config
    source = extract_relations(original_text, language)
    target = extract_relations(candidate_text, language)
    violations: list[Violation] = []
    for relation in source:
        exact = next(
            (
                item
                for item in target
                if item.subject.lower() == relation.subject.lower()
                and item.relation == relation.relation
                and item.object.lower() == relation.object.lower()
            ),
            None,
        )
        if exact:
            continue
        same_relation = [item for item in target if item.relation == relation.relation]
        role_swap = next(
            (
                item
                for item in same_relation
                if relation.relation == "responsible_for"
                and item.object.lower() == relation.object.lower()
                and item.subject.lower() != relation.subject.lower()
            ),
            None,
        )
        model_role_swap = next(
            (
                item
                for item in same_relation
                if relation.relation == "has_role"
                and item.subject.lower() == relation.subject.lower()
                and item.object.lower() != relation.object.lower()
            ),
            None,
        )
        if role_swap or model_role_swap:
            changed = role_swap if role_swap is not None else model_role_swap
            assert changed is not None
            violations.append(
                Violation(
                    code="ROLE_SWAP" if role_swap else "MODEL_ROLE_SWAP",
                    severity=RiskLevel.CRITICAL,
                    category="relation",
                    message="Candidate changed an explicit role assignment.",
                    original_span=relation.evidence,
                    candidate_span=changed.evidence,
                    evidence={"relation": relation.relation},
                    confidence=min(relation.confidence, changed.confidence),
                )
            )
            continue
        swapped = next(
            (
                item
                for item in same_relation
                if item.subject.lower() == relation.object.lower()
                or item.object.lower() == relation.subject.lower()
            ),
            None,
        )
        if swapped:
            code = (
                "ROLE_SWAP"
                if relation.relation in {"responsible_for", "has_role"}
                else "RELATION_SWAP"
            )
            violations.append(
                Violation(
                    code=code,
                    severity=RiskLevel.CRITICAL,
                    category="relation",
                    message="Candidate swapped an explicit entity relation.",
                    original_span=relation.evidence,
                    candidate_span=swapped.evidence,
                    evidence={"relation": relation.relation},
                    confidence=min(relation.confidence, swapped.confidence),
                )
            )
        elif not same_relation:
            violations.append(
                Violation(
                    code="RELATION_REMOVED",
                    severity=RiskLevel.CRITICAL,
                    category="relation",
                    message="Candidate removed an explicit relation.",
                    original_span=relation.evidence,
                    confidence=relation.confidence,
                )
            )
        else:
            violations.append(
                Violation(
                    code="RELATION_CHANGED",
                    severity=RiskLevel.HIGH,
                    category="relation",
                    message="Candidate changed an explicit relation value.",
                    original_span=relation.evidence,
                    candidate_span=same_relation[0].evidence,
                    confidence=relation.confidence,
                )
            )
    return violations
