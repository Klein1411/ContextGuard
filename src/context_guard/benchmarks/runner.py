from __future__ import annotations

import csv
import json
import platform
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from context_guard import ContextGuard, GuardConfig, SafetyStatus
from context_guard.adapters.mutations import generate_mutations


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
    label_status: str = "synthetic"


def _cases(seed: int = 20260729) -> list[MutationCase]:
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


def run_benchmark(output: Path, seed: int = 20260729) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    cases = _cases(seed)
    predictions: list[dict[str, object]] = []
    started = perf_counter()
    for case in cases:
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
            }
        )
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
    metrics = {
        "sample_count": len(cases),
        "safe_count": safe,
        "unsafe_count": unsafe,
        "false_acceptance_rate": false_accept / unsafe if unsafe else 0.0,
        "unsafe_detection_recall": unsafe_detected / unsafe if unsafe else 0.0,
        "false_rejection_rate": false_reject / safe if safe else 0.0,
        "elapsed_ms": round(elapsed_ms, 3),
    }
    now = datetime.now(UTC)
    manifest = {
        "run_id": now.strftime("%Y%m%dT%H%M%SZ"),
        "timestamp": now.isoformat(),
        "python_version": sys.version,
        "os": platform.platform(),
        "seed": seed,
        "dataset_version": "synthetic-v0",
        "policy": "strict",
        "profile": "mixed",
        "metrics": metrics,
        "label_status": "synthetic",
    }
    (output / "benchmark_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "verified_predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in predictions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)
    (output / "per_category_metrics.csv").write_text(
        f"category,sample_count\nsynthetic,{len(cases)}\n", encoding="utf-8"
    )
    return manifest
