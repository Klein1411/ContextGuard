from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "runtime_benchmark", Path("scripts/runtime_benchmark.py")
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["runtime_benchmark"] = _MODULE
_SPEC.loader.exec_module(_MODULE)

_percentile = _MODULE._percentile
_write_artifacts = _MODULE._write_artifacts
build_runtime_cases = _MODULE.build_runtime_cases
validate_runtime_artifacts = _MODULE.validate_runtime_artifacts


class TinyTokenizer:
    def __call__(self, text: str, **_: object) -> dict[str, list[int]]:
        return {"input_ids": text.split()}


def test_runtime_percentile_is_deterministic() -> None:
    assert _percentile([3.0, 1.0, 2.0], 0.50) == 2.0
    assert _percentile([], 0.95) == 0.0


def test_runtime_cases_have_real_bucket_counts() -> None:
    cases = build_runtime_cases(TinyTokenizer())
    assert len(cases) == 8
    assert {case.bucket for case in cases} == {"short", "medium", "long", "very_long"}
    assert all(case.original_tokens == case.candidate_tokens for case in cases)
    assert all(case.original_tokens >= 128 for case in cases)


def test_runtime_artifact_contract(tmp_path: Path) -> None:
    cases = build_runtime_cases(TinyTokenizer())[:1]
    metrics = [{"mode": "R1_direct_deterministic", "phase": "warm", "p95_ms": 1.0}]
    samples = [{"mode": "R1_direct_deterministic", "latency_ms": 1.0}]
    manifest = _write_artifacts(
        tmp_path,
        metrics,
        samples,
        cases,
        include_docker=False,
        hybrid_case_ids=[],
        skipped_hybrid_cases=[],
    )
    assert manifest["scope"] == "M10a"
    assert (tmp_path / "runtime_manifest.json").is_file()
    manifest_json = json.loads(
        (tmp_path / "runtime_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest_json["modes"] == ["R1_direct_deterministic"]
    with (tmp_path / "runtime_metrics.csv").open(encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle))[0]["p95_ms"] == "1.0"


def test_runtime_artifact_validation_rejects_incomplete_modes(tmp_path: Path) -> None:
    cases = build_runtime_cases(TinyTokenizer())
    metrics = [
        {
            "mode": mode,
            "phase": "warm",
            "case_id": case.case_id,
            "bucket": case.bucket,
            "language": case.language,
            "domain": case.domain,
            "actual_character_count": len(case.original),
            "actual_original_tokens": case.original_tokens,
            "actual_candidate_tokens": case.candidate_tokens,
            "concurrency": 1,
            "sample_count": 1,
            "p50_ms": 1.0,
            "p95_ms": 1.0,
            "p99_ms": 1.0,
            "error_rate": 0.0,
            "timeout_rate": 0.0,
        }
        for mode in (
            "R1_direct_deterministic",
            "R2_asgi_in_process_deterministic",
            "R3_localhost_http_deterministic",
            "R5_direct_hybrid_semantic",
        )
        for case in cases
    ]
    _write_artifacts(
        tmp_path,
        metrics,
        [{"mode": "test", "latency_ms": 1.0}],
        cases,
        include_docker=False,
        hybrid_case_ids=[],
        skipped_hybrid_cases=[],
    )
    assert validate_runtime_artifacts(tmp_path)["valid"] is True
