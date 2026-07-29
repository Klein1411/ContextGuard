from __future__ import annotations

from time import perf_counter

from context_guard.normalization.text import extract_facts
from context_guard.policies.engine import action_for, status_for
from context_guard.schemas.models import AnalyzeResult, GuardConfig, ValidationResult
from context_guard.scoring.risk import risk_level, risk_score
from context_guard.validators.entity import entity_violations
from context_guard.validators.exact import exact_violations
from context_guard.validators.logic import logic_violations
from context_guard.validators.relation import relation_violations


class ContextGuard:
    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def _check_length(self, *texts: str) -> None:
        for text in texts:
            if len(text) > self.config.max_input_chars:
                raise ValueError(
                    f"Input exceeds max_input_chars={self.config.max_input_chars}; "
                    "no truncation was performed."
                )

    def analyze(
        self, text: str, *, language: str | None = None, profile: str | None = None
    ) -> AnalyzeResult:
        self._check_length(text)
        started = perf_counter()
        facts, spans, warnings, normalized_language = extract_facts(
            text, language or self.config.language
        )
        return AnalyzeResult(
            normalized_language=normalized_language,
            facts=facts,
            protected_spans=spans,
            warnings=warnings,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )

    def validate(self, original_text: str, candidate_text: str) -> ValidationResult:
        self._check_length(original_text, candidate_text)
        started = perf_counter()
        original = self.analyze(original_text)
        candidate = self.analyze(candidate_text, language=original.normalized_language)
        violations = exact_violations(original.facts, candidate.facts, self.config)
        violations.extend(entity_violations(original_text, candidate_text, self.config))
        violations.extend(
            logic_violations(
                original_text, candidate_text, original.normalized_language, self.config
            )
        )
        violations.extend(
            relation_violations(
                original_text, candidate_text, original.normalized_language, self.config
            )
        )
        warnings = sorted(set(original.warnings + candidate.warnings))
        status = status_for(violations, warnings, self.config.policy)
        score = risk_score(violations)
        level = risk_level(score, violations)
        return ValidationResult(
            status=status,
            risk_score=score,
            risk_level=level,
            violations=violations,
            warnings=warnings,
            recommended_action=action_for(status, self.config.policy, violations),
            normalized_language=original.normalized_language,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            reason_codes=[violation.code for violation in violations],
        )
