import json
from collections import Counter
from pathlib import Path

import pytest

from context_guard import ContextGuard, GuardConfig
from context_guard.adapters.semantic import UnavailableSemanticVerifier
from context_guard.benchmarks.dataset import (
    build_provisional_mutations,
    load_jsonl,
    validate_dataset,
    validate_mutation_dataset,
)
from context_guard.benchmarks.hybrid import run_hybrid_benchmark
from context_guard.benchmarks.runner import promote_run, run_benchmark, validate_run_artifacts


def test_tier_a_contract() -> None:
    records = load_jsonl(Path("benchmarks/datasets/golden_v0_provisional.jsonl"))
    summary = validate_dataset(records)
    assert summary["sample_count"] == 300
    assert Counter(record["domain"] for record in records) == {
        "general": 75,
        "academic": 75,
        "business": 75,
        "technical": 75,
    }


def test_audited_tier_a_contract() -> None:
    records = load_jsonl(Path("benchmarks/datasets/golden_v0_audited.jsonl"))
    summary = validate_dataset(records)
    assert summary["sample_count"] == 300
    assert summary["label_statuses"] == ["audited"]


def test_hybrid_audited_dataset_contract() -> None:
    records = load_jsonl(Path("benchmarks/datasets/hybrid_v0_audited.jsonl"))
    assert len(records) == 100
    assert Counter(record["label"] for record in records) == {"SAFE": 50, "UNSAFE": 50}
    assert {record["label_status"] for record in records} == {"audited"}
    guard = ContextGuard(GuardConfig(language="auto", profile="general"))
    assert all(
        guard.validate(record["original"], record["candidate"]).status.value == "UNCERTAIN"
        for record in records
    )


def test_hybrid_final_artifact_contract() -> None:
    manifest = json.loads(Path("artifacts/final/hybrid_manifest.json").read_text(encoding="utf-8"))
    predictions = (
        Path("artifacts/final/hybrid_predictions.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert manifest["sample_count"] == 100
    assert manifest["label_statuses"] == ["audited"]
    assert manifest["metric_only"] is True
    assert len(predictions) == 100


def test_tier_b_contract() -> None:
    records = load_jsonl(Path("benchmarks/datasets/mutation_v0_provisional.jsonl"))
    summary = validate_mutation_dataset(records)
    assert int(summary["sample_count"]) >= 2000
    assert int(summary["unique_candidates"]) == int(summary["sample_count"])
    assert any(
        record["label"] == "SAFE" and record["violation_types"] == ["safe_date_format"]
        for record in records
    )


def test_mutation_generation_is_reproducible() -> None:
    first = build_provisional_mutations(seed=20260729, minimum=2000)
    second = build_provisional_mutations(seed=20260729, minimum=2000)
    assert first == second


def test_benchmark_artifact_contract(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run_benchmark(output, dataset=Path("benchmarks/datasets/golden_v0_provisional.jsonl"))
    result = validate_run_artifacts(output, expected_sample_count=300)
    assert result["valid"] is True
    manifest = json.loads((output / "benchmark_manifest.json").read_text(encoding="utf-8"))
    assert manifest["quality_gate"]["critical_metrics_pass"] is True
    assert manifest["quality_gate"]["label_status_allows_final_promotion"] is False
    category_csv = (output / "per_category_metrics.csv").read_text(encoding="utf-8")
    assert "metric_group" in category_csv


def test_unverified_run_cannot_be_promoted(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run_benchmark(output, dataset=Path("benchmarks/datasets/golden_v0_provisional.jsonl"))
    with pytest.raises(ValueError, match="label_status"):
        promote_run(output, tmp_path / "final")


def test_audited_run_can_be_promoted(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run_benchmark(output, dataset=Path("benchmarks/datasets/golden_v0_audited.jsonl"))
    result = promote_run(output, tmp_path / "final")
    assert result["promoted"] is True


def test_hybrid_benchmark_keeps_unavailable_verifier_safe(tmp_path: Path) -> None:
    output = tmp_path / "hybrid"
    result = run_hybrid_benchmark(
        [
            {
                "id": "uncertain-1",
                "original": "Deadline 03/04/2026.",
                "candidate": "Deadline 03/04/2026.",
                "label": "SAFE",
                "label_status": "unverified",
            }
        ],
        UnavailableSemanticVerifier(),
        output=output,
    )
    assert result["sample_count"] == 1
    assert result["semantic_calls"] == 0
    assert result["label_status_allows_final_promotion"] is False
    assert (output / "hybrid_manifest.json").is_file()
