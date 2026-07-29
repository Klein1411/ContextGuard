from context_guard.adapters import RuleBasedCompressor, generate_mutations


def test_rule_based_compressor_is_deterministic() -> None:
    compressor = RuleBasedCompressor()
    text = "Um, first fact. Second fact. Third fact."
    assert compressor.compress(text) == compressor.compress(text)


def test_mutation_records_are_replayable() -> None:
    mutations = generate_mutations(
        "Do not deploy Python 3.11 if accuracy is at least 90% unless Alice approves the release.",
        seed=7,
    )
    assert mutations
    assert all(m.expected_label == "UNSAFE" and m.source_span and m.candidate for m in mutations)
    assert any(m.mutation_type == "negation_removed" for m in mutations)
