from __future__ import annotations

from context_guard.extraction.entities import extract_entities
from context_guard.schemas.models import GuardConfig, RiskLevel, Violation


def entity_violations(
    original_text: str, candidate_text: str, config: GuardConfig
) -> list[Violation]:
    del config
    source = extract_entities(original_text)
    target = extract_entities(candidate_text)
    violations: list[Violation] = []
    missing = [
        entity for entity in source if entity.lower() not in {item.lower() for item in target}
    ]
    replacements = [
        item for item in target if item.lower() not in {entity.lower() for entity in source}
    ]
    for index, entity in enumerate(missing):
        replacement = replacements[index] if index < len(replacements) else None
        violations.append(
            Violation(
                code="ENTITY_CHANGED" if replacement else "ENTITY_REMOVED",
                severity=RiskLevel.HIGH,
                category="entity",
                message="Candidate changed or removed an explicit entity.",
                original_span=entity,
                candidate_span=replacement,
                evidence={"source_entities": source, "candidate_entities": target},
                confidence=0.8,
            )
        )
    return violations
