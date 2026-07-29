import pytest

from context_guard import (
    ContextGuard,
    GuardConfig,
    RecommendedAction,
    RiskLevel,
    SafetyStatus,
    ValidationResult,
)
from context_guard.adapters import (
    AdapterUnavailableError,
    CompressorAdapter,
    LLMSummarizerCompressor,
    RuleBasedCompressor,
    TokenLevelCompressor,
    generate_mutations,
)
from context_guard.adapters.base import SemanticVerification
from context_guard.benchmarks.candidates import build_unverified_candidates, validate_candidates
from context_guard.benchmarks.dataset import build_provisional_golden


def test_rule_based_compressor_is_deterministic() -> None:
    compressor = RuleBasedCompressor()
    text = "Um, first fact. Second fact. Third fact."
    assert compressor.compress(text) == compressor.compress(text)


def test_rule_based_compressor_keeps_protected_fact_sentence() -> None:
    text = "First filler. Must use Python 3.11. Third filler."
    protected = ContextGuard(GuardConfig(language="en", profile="technical")).analyze(text)
    candidate = RuleBasedCompressor().compress(text, protected.protected_spans)
    assert "Python 3.11" in candidate


@pytest.mark.parametrize("adapter", [TokenLevelCompressor(), LLMSummarizerCompressor()])
def test_optional_compressor_fails_explicitly(adapter: CompressorAdapter) -> None:
    with pytest.raises(AdapterUnavailableError, match="unavailable"):
        adapter.compress("text")


class _FakeSemanticVerifier:
    name = "fake"

    def __init__(self, result: ValidationResult | None) -> None:
        self.calls = 0
        self.result = result

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification:
        del original_text, candidate_text
        self.calls += 1
        return SemanticVerification(available=True, result=self.result)


def test_semantic_verifier_runs_only_for_uncertain() -> None:
    semantic_result = ValidationResult(
        status=SafetyStatus.PASS,
        risk_score=0.0,
        risk_level=RiskLevel.LOW,
        violations=[],
        recommended_action=RecommendedAction.ACCEPT_CANDIDATE,
        normalized_language="vi",
        latency_ms=1.0,
    )
    verifier = _FakeSemanticVerifier(semantic_result)
    guard = ContextGuard(GuardConfig(language="vi"))
    uncertain = guard.validate_with_semantic(
        "Deadline 03/04/2026.", "Deadline 03/04/2026.", verifier
    )
    assert uncertain.status is SafetyStatus.PASS
    assert verifier.calls == 1

    fail = guard.validate_with_semantic("Use Python 3.11.", "Use Python 3.12.", verifier)
    assert fail.status is SafetyStatus.FAIL
    assert verifier.calls == 1


def test_rule_based_tier_c_candidates_remain_unverified() -> None:
    records = build_unverified_candidates(build_provisional_golden()[:4], RuleBasedCompressor())
    summary = validate_candidates(records)
    assert summary["sample_count"] == 4
    assert summary["label_statuses"] == ["unverified"]


def test_mutation_records_are_replayable() -> None:
    mutations = generate_mutations(
        "Do not deploy Python 3.11 if accuracy is at least 90% unless Alice approves the release.",
        seed=7,
    )
    assert mutations
    assert all(m.expected_label == "UNSAFE" and m.source_span and m.candidate for m in mutations)
    assert any(m.mutation_type == "negation_removed" for m in mutations)
