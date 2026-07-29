"""M13 compressor/token-saving benchmark with explicit safety and fallback metrics."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from context_guard import ContextGuard, GuardConfig
from context_guard.adapters import (
    AdapterUnavailableError,
    LLMLingua2Compressor,
    RuleBasedCompressor,
)
from context_guard.storage import ensure_data_home, get_data_home

RATES = (0.33, 0.50, 0.70)
MODES = ("R6_direct_compressor", "R7_direct_guard", "R8_api_guard", "R9_direct_api_guard")
QWEN_TOKENIZER = "Qwen/Qwen2.5-0.5B-Instruct"
LLMLINGUA_MAX_INPUT_TOKENS = 512


@dataclass
class SampleMetric:
    sample_id: str
    source_name: str
    domain: str
    language: str
    compressor: str
    rate: float
    protected: bool
    mode: str
    original_tokens: int
    candidate_tokens: int
    gross_saved_tokens: int
    gross_saving_ratio: float
    safe_effective_saved_tokens: int
    safe_saving_ratio: float
    guard_status: str
    protected_spans: int
    protected_retained: bool
    fallback: bool
    fallback_reason: str
    latency_ms: float


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _tokenizer(model_id: str, local_files_only: bool) -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_id, local_files_only=local_files_only)


def _select_records(data_home: Path, limit: int) -> list[dict[str, Any]]:
    rows = _read_jsonl(data_home / "normalized" / "natural_adversarial_v1_dev.jsonl")
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["domain"], row["language"])
        if key not in seen or len(selected) < limit:
            selected.append(row)
            seen.add(key)
        if len(selected) >= limit:
            break
    return selected


def _guard_result(original: str, candidate: str, row: dict[str, Any]) -> tuple[str, float]:
    started = time.perf_counter()
    config = GuardConfig(
        language=row["language"], profile=row["domain"], policy="strict"
    )
    result = ContextGuard(config).validate(original, candidate)
    return result.status.value, (time.perf_counter() - started) * 1000


async def _api_guard(
    client: Any,
    original: str,
    candidate: str,
    row: dict[str, Any],
) -> tuple[str, float]:
    started = time.perf_counter()
    response = await client.post(
        "/v1/validate",
        json={
            "original_text": original,
            "candidate_text": candidate,
            "language": row["language"],
            "profile": row["domain"],
            "policy": "strict",
        },
    )
    response.raise_for_status()
    return response.json()["status"], (time.perf_counter() - started) * 1000


def _tokens(tokenizer: Any, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


def _metric(
    *,
    row: dict[str, Any],
    compressor: str,
    rate: float,
    protected: bool,
    mode: str,
    original_tokens: int,
    candidate: str,
    candidate_tokens: int,
    status: str,
    protected_count: int,
    protected_retained: bool,
    fallback: bool,
    fallback_reason: str,
    latency_ms: float,
) -> SampleMetric:
    gross = max(original_tokens - candidate_tokens, 0)
    safe = gross if status == "PASS" else 0
    original_safe = max(original_tokens, 1)
    return SampleMetric(
        sample_id=row["sample_id"],
        source_name=row["source_name"],
        domain=row["domain"],
        language=row["language"],
        compressor=compressor,
        rate=rate,
        protected=protected,
        mode=mode,
        original_tokens=original_tokens,
        candidate_tokens=candidate_tokens,
        gross_saved_tokens=gross,
        gross_saving_ratio=gross / original_safe,
        safe_effective_saved_tokens=safe,
        safe_saving_ratio=safe / original_safe,
        guard_status=status,
        protected_spans=protected_count,
        protected_retained=protected_retained,
        fallback=fallback,
        fallback_reason=fallback_reason,
        latency_ms=latency_ms,
    )


def _compress(
    compressor: Any,
    text: str,
    protected_spans: list[Any],
) -> tuple[str, bool, str, float]:
    started = time.perf_counter()
    try:
        candidate = compressor.compress(text, protected_spans)
        return candidate, False, "", (time.perf_counter() - started) * 1000
    except (AdapterUnavailableError, RuntimeError, ValueError) as exc:
        return text, True, f"{type(exc).__name__}: {exc}", (time.perf_counter() - started) * 1000


async def _run_async(
    rows: list[dict[str, Any]],
    metrics: list[SampleMetric],
    tokenizer: Any,
    local_files_only: bool,
    ablation_limit: int,
) -> None:
    import httpx

    from context_guard.api.app import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://contextguard") as client:
        for rate in RATES:
            compressors: list[tuple[str, Any]] = [("rule-based", RuleBasedCompressor())]
            compressors.append(
                ("llmlingua-2", LLMLingua2Compressor(rate=rate, local_files_only=local_files_only))
            )
            for compressor_name, compressor in compressors:
                for index, row in enumerate(rows):
                    original = row["original_context"]
                    guard = ContextGuard(
                        GuardConfig(language=row["language"], profile=row["domain"])
                    )
                    spans = guard.analyze(original).protected_spans
                    original_tokens = _tokens(tokenizer, original)
                    protected_values = (
                        (True, False)
                        if compressor_name == "rule-based" and index < ablation_limit
                        else (True,)
                    )
                    for protected in protected_values:
                        if (
                            compressor_name == "llmlingua-2"
                            and original_tokens > LLMLINGUA_MAX_INPUT_TOKENS
                        ):
                            candidate = original
                            fallback = True
                            fallback_reason = (
                                f"MODEL_MAX_INPUT_TOKENS_{LLMLINGUA_MAX_INPUT_TOKENS}"
                            )
                            latency = 0.0
                        else:
                            candidate, fallback, fallback_reason, latency = _compress(
                                compressor, original, spans if protected else []
                            )
                        candidate_tokens = _tokens(tokenizer, candidate)
                        retained = all(span.text in candidate for span in spans if span.text)
                        direct_status, direct_guard_latency = _guard_result(
                            original, candidate, row
                        )
                        api_status, api_latency = await _api_guard(client, original, candidate, row)
                        for mode, status, guard_latency in (
                            ("R6_direct_compressor", "NOT_RUN", 0.0),
                            ("R7_direct_guard", direct_status, direct_guard_latency),
                            ("R8_api_guard", api_status, api_latency),
                            ("R9_direct_api_guard", api_status, api_latency + latency),
                        ):
                            metrics.append(
                                _metric(
                                    row=row,
                                    compressor=compressor_name,
                                    rate=rate,
                                    protected=protected,
                                    mode=mode,
                                    original_tokens=original_tokens,
                                    candidate=candidate,
                                    candidate_tokens=candidate_tokens,
                                    status=status,
                                    protected_count=len(spans),
                                    protected_retained=retained,
                                    fallback=fallback,
                                    fallback_reason=fallback_reason,
                                    latency_ms=latency + guard_latency,
                                )
                            )


def run(data_home: Path, output_dir: Path, limit: int, local_files_only: bool) -> dict[str, Any]:
    os.environ.setdefault("HF_HOME", str(data_home / "model_cache" / "huggingface"))
    rows = _select_records(data_home, limit)
    tokenizer = _tokenizer(QWEN_TOKENIZER, local_files_only)
    metrics: list[SampleMetric] = []
    asyncio.run(_run_async(rows, metrics, tokenizer, local_files_only, min(8, len(rows))))
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "m13_compressor_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(metrics[0])))
        writer.writeheader()
        writer.writerows(asdict(item) for item in metrics)
    samples_path = output_dir / "m13_compressor_samples.jsonl"
    with samples_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in metrics:
            handle.write(json.dumps(asdict(item), ensure_ascii=False, sort_keys=True) + "\n")
    fallback_count = sum(item.fallback for item in metrics)
    grouped: dict[tuple[str, float, str], list[SampleMetric]] = defaultdict(list)
    for item in metrics:
        if item.mode in {"R7_direct_guard", "R8_api_guard"} and item.protected:
            grouped[(item.compressor, item.rate, item.mode)].append(item)
    pareto_points = []
    for (compressor, rate, mode), group in sorted(grouped.items()):
        latencies = sorted(item.latency_ms for item in group)
        point = {
            "compressor": compressor,
            "rate": rate,
            "mode": mode,
            "mean_gross_saving_ratio": sum(item.gross_saving_ratio for item in group) / len(group),
            "mean_safe_saving_ratio": sum(item.safe_saving_ratio for item in group) / len(group),
            "pass_rate": sum(item.guard_status == "PASS" for item in group) / len(group),
            "p95_latency_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)],
        }
        pareto_points.append(point)
    summary = {
        "scope": "M13",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "records": len(rows),
        "metric_rows": len(metrics),
        "compressors": ["rule-based", "llmlingua-2"],
        "rates": list(RATES),
        "modes": list(MODES),
        "tokenizer": {"model": QWEN_TOKENIZER, "local_files_only": local_files_only},
        "llmlingua_max_input_tokens": LLMLINGUA_MAX_INPUT_TOKENS,
        "protected_span_ablation": (
            "RuleBasedCompressor protected=true/false on first 8 records; "
            "LLMLingua-2 uses protected spans."
        ),
        "fallback_rows": fallback_count,
        "fallback_rate": fallback_count / len(metrics) if metrics else 1.0,
        "pareto_points": pareto_points,
        "files": {"metrics": str(csv_path), "samples": str(samples_path)},
        "break_even": {
            "status": "not_measured_no_target_llm_in_scope",
            "limitation": (
                "No downstream target LLM/API token-cost and latency contract was supplied; "
                "compressor-only Pareto is reported without monetary break-even."
            ),
        },
        "limitations": [
            "safe_effective_saved_tokens is zero unless deterministic guard returns PASS",
            "LLMLingua-2 fallback is retained per sample and never converted to a success",
            "Results are a bounded pilot, not a production compression-quality claim",
        ],
    }
    manifest_path = output_dir / "m13_compressor_manifest.json"
    manifest_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    public_dir = Path(__file__).resolve().parents[1] / "artifacts" / "final"
    public_dir.mkdir(parents=True, exist_ok=True)
    for source in (manifest_path, csv_path, samples_path):
        (public_dir / source.name).write_bytes(source.read_bytes())
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-home", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path(".runtime/m13_compressor"))
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    summary = run(
        ensure_data_home(args.data_home or get_data_home()),
        args.output,
        args.limit,
        args.local_files_only,
    )
    print(
        json.dumps(
            {
                "valid": True,
                "records": summary["records"],
                "metric_rows": summary["metric_rows"],
                "fallback_rate": summary["fallback_rate"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
