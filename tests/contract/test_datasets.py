from pathlib import Path

import pytest

from context_guard.benchmarks.dataset import (
    build_provisional_mutations,
    load_jsonl,
    validate_dataset,
    validate_mutation_dataset,
)
from context_guard.benchmarks.runner import promote_run, run_benchmark, validate_run_artifacts


def test_tier_a_contract() -> None:
    records = load_jsonl(Path("benchmarks/datasets/golden_v0_provisional.jsonl"))
    summary = validate_dataset(records)
    assert summary["sample_count"] == 300


def test_tier_b_contract() -> None:
    records = load_jsonl(Path("benchmarks/datasets/mutation_v0_provisional.jsonl"))
    summary = validate_mutation_dataset(records)
    assert int(summary["sample_count"]) >= 2000
    assert int(summary["unique_candidates"]) == int(summary["sample_count"])


def test_mutation_generation_is_reproducible() -> None:
    first = build_provisional_mutations(seed=20260729, minimum=2000)
    second = build_provisional_mutations(seed=20260729, minimum=2000)
    assert first == second


def test_benchmark_artifact_contract(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run_benchmark(output, dataset=Path("benchmarks/datasets/golden_v0_provisional.jsonl"))
    result = validate_run_artifacts(output, expected_sample_count=300)
    assert result["valid"] is True


def test_unverified_run_cannot_be_promoted(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run_benchmark(output, dataset=Path("benchmarks/datasets/golden_v0_provisional.jsonl"))
    with pytest.raises(ValueError, match="label_status"):
        promote_run(output, tmp_path / "final")
