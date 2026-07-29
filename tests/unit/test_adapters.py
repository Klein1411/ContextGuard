import sys
from types import SimpleNamespace

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
    LLMLingua2Compressor,
    LLMSummarizerCompressor,
    RuleBasedCompressor,
    TokenLevelCompressor,
    TransformersSemanticVerifier,
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


def test_llmlingua2_adapter_is_lazy_and_safe_when_model_is_not_cached() -> None:
    compressor = LLMLingua2Compressor(local_files_only=True)
    compressor.model_id = "contextguard/nonexistent-compressor-model"
    with pytest.raises(AdapterUnavailableError, match="LLMLingua-2"):
        compressor.compress("text")


def test_llmlingua2_adapter_passes_mode_at_load_not_compress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakePromptCompressor:
        def __init__(self, **kwargs: object) -> None:
            calls["load"] = kwargs

        def compress_prompt(self, context: list[str], **kwargs: object) -> dict[str, str]:
            calls["compress"] = kwargs
            assert context == ["text"]
            return {"compressed_prompt": "text"}

    monkeypatch.setitem(
        sys.modules,
        "llmlingua",
        SimpleNamespace(PromptCompressor=FakePromptCompressor),
    )
    compressor = LLMLingua2Compressor(device="cpu", local_files_only=True)
    assert compressor.compress("text") == "text"
    assert calls["load"]["use_llmlingua2"] is True  # type: ignore[index]
    assert "use_llmlingua2" not in calls["compress"]  # type: ignore[operator]


class _FakeSemanticVerifier:
    name = "fake"

    def __init__(self, result: ValidationResult | None) -> None:
        self.calls = 0
        self.result = result

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification:
        del original_text, candidate_text
        self.calls += 1
        return SemanticVerification(available=True, result=self.result)


class _BrokenSemanticVerifier:
    name = "broken"

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification:
        del original_text, candidate_text
        raise TimeoutError("semantic timeout")


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


def test_semantic_verifier_error_keeps_safe_uncertain_fallback() -> None:
    result = ContextGuard(GuardConfig(language="vi", policy="strict")).validate_with_semantic(
        "Deadline 03/04/2026.", "Deadline 03/04/2026.", _BrokenSemanticVerifier()
    )
    assert result.status is SafetyStatus.UNCERTAIN
    assert result.recommended_action is RecommendedAction.USE_ORIGINAL
    assert "SEMANTIC_VERIFIER_ERROR" in result.reason_codes


def test_transformers_verifier_is_lazy_and_safe_when_optional_group_is_absent() -> None:
    verifier = TransformersSemanticVerifier(local_files_only=True)
    verifier.model_id = "contextguard/nonexistent-model"
    outcome = verifier.verify("The deadline is 03/04/2026.", "The deadline is 03/04/2026.")
    assert outcome.available is False
    assert outcome.result is None
    assert outcome.warning == "SEMANTIC_VERIFIER_ERROR"


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
