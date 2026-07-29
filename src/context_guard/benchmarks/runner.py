from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2
from time import perf_counter
from typing import Any

from context_guard import ContextGuard, GuardConfig, SafetyStatus
from context_guard.adapters.mutations import generate_mutations
from context_guard.benchmarks.dataset import (
    load_jsonl,
    validate_dataset,
    validate_mutation_dataset,
)

_METRIC_GROUPS = {
    "number_changed": "Numeric retention",
    "percentage_changed": "Percentage retention",
    "money_changed": "Currency retention",
    "date_changed": "Date retention",
    "safe_date_format": "Date retention",
    "unit_changed": "Unit retention",
    "negation_removed": "Negation recall",
    "condition_removed": "Constraint recall",
    "comparison_reversed": "Constraint recall",
    "modality_changed": "Constraint recall",
    "exception_removed": "Exception recall",
    "entity_changed": "Entity-role consistency",
    "responsible_changed": "Entity-role consistency",
    "model_role_changed": "Entity-role consistency",
    "filename_changed": "Technical literal retention",
    "config_changed": "Technical literal retention",
    "command_changed": "Technical literal retention",
    "boolean_changed": "Technical literal retention",
    "version_changed": "Technical literal retention",
    "relation_swap": "Relation swap detection",
}


def _metric_group(category: str) -> str:
    fallback = "SAFE transformation" if category.startswith("safe") else "Other"
    return _METRIC_GROUPS.get(category, fallback)


@dataclass(frozen=True)
class MutationCase:
    id: str
    language: str
    domain: str
    original: str
    candidate: str
    expected_label: str
    mutation_type: str
    seed: int
    source_span: str
    replacement: str
    label_status: str = "synthetic_unverified"


def _synthetic_cases(seed: int = 20260729) -> list[MutationCase]:
    rng = random.Random(seed)
    templates = [
        (
            "vi",
            "technical",
            "Kh\u00f4ng tri\u1ec3n khai n\u1ebfu accuracy th\u1ea5p h\u01a1n 90%.",
            "Tri\u1ec3n khai n\u1ebfu accuracy th\u1ea5p h\u01a1n 90%.",
            "negation_removed",
            "UNSAFE",
        ),
        (
            "en",
            "technical",
            "Do not deploy Python 3.11 when latency exceeds 50 ms.",
            "Do not deploy Python 3.12 when latency exceeds 50 ms.",
            "version_changed",
            "UNSAFE",
        ),
        (
            "vi",
            "business",
            "Thanh to\u00e1n 20 tri\u1ec7u \u0111\u1ed3ng tr\u01b0\u1edbc ng\u00e0y 30/08/2026.",
            "Thanh to\u00e1n 20 tri\u1ec7u \u0111\u1ed3ng tr\u01b0\u1edbc ng\u00e0y 2026-08-30.",
            "safe_date_format",
            "SAFE",
        ),
        (
            "en",
            "academic",
            "The model achieved 90% accuracy on XNLI.",
            "The model achieved 90% accuracy on XNLI.",
            "identity",
            "SAFE",
        ),
    ]
    cases: list[MutationCase] = []
    index = 0
    for language, domain, original, candidate, mutation, label in templates:
        cases.append(
            MutationCase(
                f"synthetic-{index:04d}",
                language,
                domain,
                original,
                candidate,
                label,
                mutation,
                rng.randrange(1_000_000_000),
                "",
                "",
            )
        )
        index += 1
        for generated in generate_mutations(original, seed=seed + index):
            cases.append(
                MutationCase(
                    f"synthetic-{index:04d}",
                    language,
                    domain,
                    original,
                    generated.candidate,
                    generated.expected_label,
                    generated.mutation_type,
                    generated.seed,
                    generated.source_span,
                    generated.replacement,
                )
            )
            index += 1
    rng.shuffle(cases)
    return [
        MutationCase(
            f"synthetic-{idx:04d}",
            case.language,
            case.domain,
            case.original,
            case.candidate,
            case.expected_label,
            case.mutation_type,
            case.seed,
            case.source_span,
            case.replacement,
            case.label_status,
        )
        for idx, case in enumerate(cases)
    ]


def _dataset_cases(path: Path, seed: int) -> list[MutationCase]:
    records = load_jsonl(path)
    if "mutation" in path.stem:
        validate_mutation_dataset(records)
    else:
        validate_dataset(records)
    return [
        MutationCase(
            id=record["id"],
            language=record["language"],
            domain=record["domain"],
            original=record["original"],
            candidate=record["candidate"],
            expected_label=record["label"],
            mutation_type=record["violation_types"][0]
            if record["violation_types"]
            else "safe_transformation",
            seed=seed + index,
            source_span=record["critical_facts"][0] if record["critical_facts"] else "",
            replacement="",
            label_status=record["label_status"],
        )
        for index, record in enumerate(records)
    ]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, int((percentile / 100) * len(ordered) + 0.999999))
    return round(ordered[min(rank, len(ordered)) - 1], 3)


def _decision_signature(predictions: list[dict[str, object]]) -> str:
    canonical = [
        {key: value for key, value in prediction.items() if key != "latency_ms"}
        for prediction in predictions
    ]
    payload = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in canonical
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _rss_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return None
    return float(round(psutil.Process().memory_info().rss / (1024 * 1024), 3))


def _load_cases(path: Path, seed: int) -> tuple[list[MutationCase], dict[str, object]]:
    records = load_jsonl(path)
    validation = (
        validate_mutation_dataset(records)
        if "mutation" in path.stem
        else validate_dataset(records)
    )
    return _dataset_cases(path, seed), validation


def run_benchmark(
    output: Path,
    seed: int = 20260729,
    dataset: Path | None = None,
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    dataset_path = dataset or Path("benchmarks/datasets/golden_v0_provisional.jsonl")
    if dataset_path.exists():
        cases, dataset_validation = _load_cases(dataset_path, seed)
    else:
        cases = _synthetic_cases(seed)
        dataset_validation = {
            "sample_count": len(cases),
            "label_statuses": sorted({case.label_status for case in cases}),
        }
    predictions: list[dict[str, object]] = []
    started = perf_counter()
    peak_ram_mb = _rss_mb()
    for case in cases:
        case_started = perf_counter()
        result = ContextGuard(GuardConfig(language=case.language, profile=case.domain)).validate(
            case.original, case.candidate
        )
        predictions.append(
            {
                "id": case.id,
                "expected_label": case.expected_label,
                "predicted_status": result.status.value,
                "risk_score": result.risk_score,
                "reason_codes": result.reason_codes,
                "label_status": case.label_status,
                "latency_ms": result.latency_ms or round((perf_counter() - case_started) * 1000, 3),
            }
        )
        current_ram_mb = _rss_mb()
        if current_ram_mb is not None:
            peak_ram_mb = max(peak_ram_mb or current_ram_mb, current_ram_mb)
    safe = unsafe = false_accept = unsafe_detected = false_reject = 0
    for case, prediction in zip(cases, predictions, strict=True):
        expected_safe = case.expected_label == "SAFE"
        predicted_pass = prediction["predicted_status"] == SafetyStatus.PASS.value
        if expected_safe:
            safe += 1
            false_reject += int(not predicted_pass)
        else:
            unsafe += 1
            false_accept += int(predicted_pass)
            unsafe_detected += int(not predicted_pass)
    elapsed_ms = (perf_counter() - started) * 1000
    predicted_unsafe = sum(
        prediction["predicted_status"] != SafetyStatus.PASS.value for prediction in predictions
    )
    metrics = {
        "sample_count": len(cases),
        "safe_count": safe,
        "unsafe_count": unsafe,
        "false_acceptance_rate": false_accept / unsafe if unsafe else 0.0,
        "unsafe_detection_recall": unsafe_detected / unsafe if unsafe else 0.0,
        "false_rejection_rate": false_reject / safe if safe else 0.0,
        "precision": unsafe_detected / predicted_unsafe if predicted_unsafe else 1.0,
        "p50_latency_ms": _percentile(
            [float(str(prediction["latency_ms"])) for prediction in predictions], 50
        ),
        "p95_latency_ms": _percentile(
            [float(str(prediction["latency_ms"])) for prediction in predictions], 95
        ),
        "fallback_rate": sum(
            prediction["predicted_status"] == SafetyStatus.UNCERTAIN.value
            for prediction in predictions
        )
        / len(predictions)
        if predictions
        else 0.0,
        "peak_ram_mb": peak_ram_mb if peak_ram_mb is not None else "not_measured",
        "peak_vram_mb": "not_measured",
        "elapsed_ms": round(elapsed_ms, 3),
    }
    by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for case, prediction in zip(cases, predictions, strict=True):
        by_category[case.mutation_type].append(
            {"expected": case.expected_label, "predicted": prediction["predicted_status"]}
        )
    category_rows: list[dict[str, object]] = []
    for category, rows in sorted(by_category.items()):
        unsafe_rows = [row for row in rows if row["expected"] == "UNSAFE"]
        safe_rows = [row for row in rows if row["expected"] == "SAFE"]
        category_rows.append(
            {
                "category": category,
                "metric_group": _metric_group(category),
                "sample_count": len(rows),
                "false_acceptance_rate": sum(
                    row["predicted"] == SafetyStatus.PASS.value for row in unsafe_rows
                )
                / len(unsafe_rows)
                if unsafe_rows
                else 0.0,
                "unsafe_detection_recall": sum(
                    row["predicted"] != SafetyStatus.PASS.value for row in unsafe_rows
                )
                / len(unsafe_rows)
                if unsafe_rows
                else 0.0,
                "false_rejection_rate": sum(
                    row["predicted"] != SafetyStatus.PASS.value for row in safe_rows
                )
                / len(safe_rows)
                if safe_rows
                else 0.0,
                "precision": sum(
                    row["predicted"] != SafetyStatus.PASS.value for row in unsafe_rows
                )
                / sum(row["predicted"] != SafetyStatus.PASS.value for row in rows)
                if sum(row["predicted"] != SafetyStatus.PASS.value for row in rows)
                else 1.0,
            }
        )
    now = datetime.now(UTC)
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        git_commit = "unknown"
    quality_gate = {
        "critical_unsafe_recall_target": 0.95,
        "false_acceptance_rate_target": 0.02,
        "p95_latency_ms_target": 50.0,
        "critical_metrics_pass": (
            float(str(metrics["unsafe_detection_recall"])) >= 0.95
            and float(str(metrics["false_acceptance_rate"])) <= 0.02
            and float(str(metrics["p95_latency_ms"])) <= 50.0
        ),
        "label_status_allows_final_promotion": False,
        "note": "Metric-only gate; contract/regression and manual-label gates are separate.",
    }
    manifest: dict[str, object] = {
        "run_id": now.strftime("%Y%m%dT%H%M%SZ"),
        "timestamp": now.isoformat(),
        "python_version": sys.version,
        "os": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "ram": peak_ram_mb if peak_ram_mb is not None else "not_measured",
        "gpu": "not_measured",
        "cuda": "not_measured",
        "git_commit": git_commit,
        "package_versions": {"context-guard": "0.1.0"},
        "seed": seed,
        "dataset_version": dataset_path.stem,
        "policy": "strict",
        "profile": "mixed",
        "model_id": None,
        "model_revision": None,
        "adapter_config": {
            "name": (
                "controlled-mutation"
                if "mutation" in dataset_path.stem
                else "provisional-golden"
            ),
            "label_status": "synthetic_unverified",
        },
        "metrics": metrics,
        "quality_gate": quality_gate,
        "label_status": "synthetic_unverified",
        "dataset_validation": dataset_validation,
        "decision_sha256": _decision_signature(predictions),
    }
    (output / "benchmark_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "environment.json").write_text(
        json.dumps(
            {
                "python_version": sys.version,
                "os": platform.platform(),
                "cpu": platform.processor() or "unknown",
                "ram": "not_measured",
                "gpu": "not_measured",
                "cuda": "not_measured",
                "peak_ram_mb": peak_ram_mb if peak_ram_mb is not None else "not_measured",
                "peak_vram_mb": "not_measured",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (output / "verified_predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in predictions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)
    with (output / "per_category_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                list(category_rows[0])
                if category_rows
                else ["category", "metric_group", "sample_count"]
            ),
        )
        writer.writeheader()
        writer.writerows(category_rows)
    return manifest


_ARTIFACT_NAMES = (
    "benchmark_manifest.json",
    "environment.json",
    "metrics.csv",
    "per_category_metrics.csv",
    "verified_predictions.jsonl",
    "summary.json",
)


def validate_run_artifacts(
    output: Path, expected_sample_count: int | None = None
) -> dict[str, object]:
    """Validate the reproducible benchmark artifact contract and recompute core metrics."""
    missing = [name for name in _ARTIFACT_NAMES if not (output / name).is_file()]
    if missing:
        raise ValueError(f"benchmark artifact missing: {', '.join(missing)}")
    manifest: dict[str, Any] = json.loads(
        (output / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    predictions = [
        json.loads(line)
        for line in (output / "verified_predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    sample_count = len(predictions)
    if expected_sample_count is not None and sample_count != expected_sample_count:
        raise ValueError(
            f"prediction sample count {sample_count} != expected {expected_sample_count}"
        )
    if manifest.get("metrics", {}).get("sample_count") != sample_count:
        raise ValueError("manifest sample_count does not match predictions")
    if manifest.get("decision_sha256") != _decision_signature(predictions):
        raise ValueError("decision_sha256 does not match predictions")
    if any(
        prediction.get("predicted_status") not in {status.value for status in SafetyStatus}
        for prediction in predictions
    ):
        raise ValueError("predictions contain unsupported safety status")
    safe_rows = [row for row in predictions if row.get("expected_label") == "SAFE"]
    unsafe_rows = [row for row in predictions if row.get("expected_label") == "UNSAFE"]
    predicted_unsafe = [
        row for row in predictions if row.get("predicted_status") != SafetyStatus.PASS.value
    ]
    recomputed = {
        "sample_count": sample_count,
        "safe_count": len(safe_rows),
        "unsafe_count": len(unsafe_rows),
        "false_acceptance_rate": sum(
            row["predicted_status"] == SafetyStatus.PASS.value for row in unsafe_rows
        )
        / len(unsafe_rows)
        if unsafe_rows
        else 0.0,
        "unsafe_detection_recall": sum(
            row["predicted_status"] != SafetyStatus.PASS.value for row in unsafe_rows
        )
        / len(unsafe_rows)
        if unsafe_rows
        else 0.0,
        "false_rejection_rate": sum(
            row["predicted_status"] != SafetyStatus.PASS.value for row in safe_rows
        )
        / len(safe_rows)
        if safe_rows
        else 0.0,
        "precision": sum(row["expected_label"] == "UNSAFE" for row in predicted_unsafe)
        / len(predicted_unsafe)
        if predicted_unsafe
        else 1.0,
    }
    manifest_metrics = manifest.get("metrics", {})
    for key, value in recomputed.items():
        if manifest_metrics.get(key) != value:
            raise ValueError(f"manifest metric {key} does not match predictions")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if summary != manifest_metrics:
        raise ValueError("summary.json does not match manifest metrics")
    with (output / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    if len(csv_rows) != 1 or int(csv_rows[0].get("sample_count", -1)) != sample_count:
        raise ValueError("metrics.csv does not match prediction sample count")
    with (output / "per_category_metrics.csv").open(encoding="utf-8", newline="") as handle:
        category_rows = list(csv.DictReader(handle))
    if category_rows and any(
        not row.get("category") or not row.get("metric_group") for row in category_rows
    ):
        raise ValueError("per_category_metrics.csv has incomplete category metadata")
    return {"valid": True, "sample_count": sample_count, "recomputed_metrics": recomputed}


def promote_run(output: Path, destination: Path = Path("artifacts/final")) -> dict[str, object]:
    """Promote only a validated, manually labelled run into the final whitelist."""
    validation = validate_run_artifacts(output)
    manifest = json.loads((output / "benchmark_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("label_status") not in {"verified", "audited"}:
        raise ValueError("refusing promotion: dataset label_status is not verified/audited")
    destination.mkdir(parents=True, exist_ok=True)
    existing = [path.name for path in destination.iterdir() if path.is_file()]
    if existing:
        raise ValueError("refusing promotion: final artifact directory is not empty")
    for name in _ARTIFACT_NAMES:
        copy2(output / name, destination / name)
    return {"promoted": True, "destination": str(destination), **validation}
