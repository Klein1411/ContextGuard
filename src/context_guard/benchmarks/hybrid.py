from __future__ import annotations

import json
import platform
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from context_guard.adapters.base import SemanticVerifierAdapter
from context_guard.core.guard import ContextGuard
from context_guard.schemas.models import GuardConfig, SafetyStatus


def _rss_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return None
    rss = float(psutil.Process().memory_info().rss)
    return float(round(rss / (1024 * 1024), 3))


def _peak_vram_mb(verifier: SemanticVerifierAdapter) -> float | None:
    torch_module = getattr(verifier, "_torch", None)
    if torch_module is None:
        return None
    torch = cast(Any, torch_module)
    try:
        if not bool(torch.cuda.is_available()):
            return None
        allocated = float(torch.cuda.max_memory_allocated() / (1024 * 1024))
        reserved = float(torch.cuda.max_memory_reserved() / (1024 * 1024))
        return float(round(max(allocated, reserved), 3))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _metric(rows: list[dict[str, object]], status_key: str) -> dict[str, float | int]:
    safe = [row for row in rows if row["expected_label"] == "SAFE"]
    unsafe = [row for row in rows if row["expected_label"] == "UNSAFE"]
    predicted_unsafe = [row for row in rows if row[status_key] != SafetyStatus.PASS.value]
    false_accept = sum(row[status_key] == SafetyStatus.PASS.value for row in unsafe)
    detected = sum(row[status_key] != SafetyStatus.PASS.value for row in unsafe)
    false_reject = sum(row[status_key] != SafetyStatus.PASS.value for row in safe)
    return {
        "sample_count": len(rows),
        "safe_count": len(safe),
        "unsafe_count": len(unsafe),
        "false_acceptance_rate": false_accept / len(unsafe) if unsafe else 0.0,
        "unsafe_detection_recall": detected / len(unsafe) if unsafe else 0.0,
        "false_rejection_rate": false_reject / len(safe) if safe else 0.0,
        "precision": (
            sum(row["expected_label"] == "UNSAFE" for row in predicted_unsafe)
            / len(predicted_unsafe)
            if predicted_unsafe
            else 1.0
        ),
    }


def run_hybrid_benchmark(
    cases: Iterable[dict[str, object]],
    verifier: SemanticVerifierAdapter,
    *,
    config: GuardConfig | None = None,
    output: Path | None = None,
) -> dict[str, object]:
    """Compare deterministic and optional semantic paths on labelled cases.

    The caller owns label provenance. Results are explicitly marked as metric-only;
    this function never promotes candidates or treats semantic output as ground truth.
    """
    guard = ContextGuard(config or GuardConfig())
    rows: list[dict[str, object]] = []
    latencies: list[float] = []
    peak_rss = _rss_mb()
    peak_vram: float | None = None
    semantic_calls = 0
    for case in cases:
        original = str(case["original"])
        candidate = str(case["candidate"])
        started = perf_counter()
        deterministic = guard.validate(original, candidate)
        hybrid = guard.validate_with_semantic(original, candidate, verifier)
        semantic_used = "SEMANTIC_VERIFIER_USED" in hybrid.warnings
        semantic_calls += int(semantic_used)
        rows.append(
            {
                "id": case.get("id"),
                "expected_label": case.get("label", case.get("expected_label", "UNVERIFIED")),
                "label_status": case.get("label_status", "unverified"),
                "deterministic_status": deterministic.status.value,
                "hybrid_status": hybrid.status.value,
                "semantic_used": semantic_used,
                "reason_codes": hybrid.reason_codes,
            }
        )
        latencies.append(round((perf_counter() - started) * 1000, 3))
        current_rss = _rss_mb()
        if current_rss is not None:
            peak_rss = max(peak_rss or current_rss, current_rss)
        current_vram = _peak_vram_mb(verifier)
        if current_vram is not None:
            peak_vram = max(peak_vram or current_vram, current_vram)
    label_statuses = sorted({str(row["label_status"]) for row in rows})
    result: dict[str, object] = {
        "sample_count": len(rows),
        "label_statuses": label_statuses,
        "label_status_allows_final_promotion": bool(rows)
        and set(label_statuses) <= {"verified", "audited"},
        "deterministic_metrics": _metric(rows, "deterministic_status"),
        "hybrid_metrics": _metric(rows, "hybrid_status"),
        "deterministic_status_counts": dict(Counter(row["deterministic_status"] for row in rows)),
        "hybrid_status_counts": dict(Counter(row["hybrid_status"] for row in rows)),
        "semantic_calls": semantic_calls,
        "fallback_rate": sum(row["hybrid_status"] == SafetyStatus.UNCERTAIN.value for row in rows)
        / len(rows)
        if rows
        else 0.0,
        "p50_latency_ms": sorted(latencies)[max(0, int(len(latencies) * 0.50 + 0.999999) - 1)]
        if latencies
        else 0.0,
        "p95_latency_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95 + 0.999999) - 1)]
        if latencies
        else 0.0,
        "peak_ram_mb": peak_rss if peak_rss is not None else "not_measured",
        "peak_vram_mb": peak_vram if peak_vram is not None else "not_measured",
        "adapter": getattr(verifier, "name", type(verifier).__name__),
        "model_id": getattr(verifier, "model_id", None),
        "model_revision": getattr(verifier, "model_revision", None),
        "python_version": sys.version,
        "os": platform.platform(),
        "metric_only": True,
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "hybrid_manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "hybrid_predictions.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
    return result
