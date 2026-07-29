"""Run the M10a runtime matrix without changing the public V1 API.

The script deliberately measures R1-R5 only. Compressor end-to-end modes R6-R9
belong to M13 where tokenizer and safe-saving semantics are defined.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import platform
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from context_guard import ContextGuard, GuardConfig
from context_guard.adapters.semantic import TransformersSemanticVerifier
from context_guard.api.app import create_app
from context_guard.schemas.models import ValidationResult

TOKENIZER_MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
TOKENIZER_REVISION = "add259b"
BUCKET_TARGETS = {"short": 128, "medium": 512, "long": 2048, "very_long": 8192}
DETERMINISTIC_CONCURRENCY = (1, 2, 4, 8, 16)
SEMANTIC_CONCURRENCY = (1, 2, 4)


@dataclass(frozen=True)
class RuntimeCase:
    case_id: str
    bucket: str
    language: str
    domain: str
    original: str
    candidate: str
    original_tokens: int
    candidate_tokens: int


def _percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return round(ordered[index], 3)


def _sha256_texts(cases: Iterable[RuntimeCase]) -> str:
    digest = hashlib.sha256()
    for case in cases:
        digest.update(case.case_id.encode("utf-8"))
        digest.update(case.original.encode("utf-8"))
        digest.update(case.candidate.encode("utf-8"))
    return digest.hexdigest()


def _load_tokenizer(local_files_only: bool) -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        TOKENIZER_MODEL_ID,
        revision=TOKENIZER_REVISION,
        local_files_only=local_files_only,
        use_fast=False,
    )


def _token_count(tokenizer: Any, text: str) -> int:
    encoded = tokenizer(text, add_special_tokens=False, return_attention_mask=False)
    return len(encoded["input_ids"])


def _base_paragraph(index: int, language: str) -> str:
    if language == "vi":
        return (
            f"Mục vận hành {index}: triển khai ContextGuard phiên bản 0.1.{index % 10} "
            f"trên Python 3.11; chỉ chấp nhận khi p95 dưới {40 + index % 9} ms, "
            f"giữ nguyên đường dẫn D:\\services\\guard\\run-{index:04d} và cảnh báo "
            "không được bỏ qua lỗi xác thực."
        )
    return (
        f"Runbook entry {index}: deploy ContextGuard release 0.1.{index % 10} on Python 3.11; "
        f"accept only when p95 stays below {40 + index % 9} ms, preserve "
        f"D:\\services\\guard\\run-{index:04d}, and never suppress validation failures."
    )


def _build_document(target_tokens: int, language: str, tokenizer: Any) -> str:
    parts = [
        (
            "Tài liệu này mô tả quy trình triển khai, kiểm tra ngưỡng, trách nhiệm rollback "
            "và các giới hạn bảo toàn dữ kiện."
            if language == "vi"
            else "This document describes deployment checks, thresholds, rollback ownership, "
            "and the limits of fact preservation."
        )
    ]
    index = 0
    while _token_count(tokenizer, "\n".join(parts)) < target_tokens:
        parts.append(_base_paragraph(index, language))
        index += 1
    return "\n".join(parts)


def build_runtime_cases(tokenizer: Any) -> list[RuntimeCase]:
    cases: list[RuntimeCase] = []
    for bucket, target in BUCKET_TARGETS.items():
        for language in ("en", "vi"):
            domain = "technical" if language == "en" else "business"
            document = _build_document(target, language, tokenizer)
            cases.append(
                RuntimeCase(
                    case_id=f"{bucket}-{language}",
                    bucket=bucket,
                    language=language,
                    domain=domain,
                    original=document,
                    candidate=document,
                    original_tokens=_token_count(tokenizer, document),
                    candidate_tokens=_token_count(tokenizer, document),
                )
            )
    return cases


def build_uncertain_cases(cases: Iterable[RuntimeCase], tokenizer: Any) -> list[RuntimeCase]:
    uncertain: list[RuntimeCase] = []
    for case in cases:
        suffix = "\nDeadline 03/04/2026."
        original = case.original + suffix
        uncertain.append(
            RuntimeCase(
                case_id=f"{case.case_id}-uncertain",
                bucket=case.bucket,
                language=case.language,
                domain=case.domain,
                original=original,
                candidate=original,
                original_tokens=_token_count(tokenizer, original),
                candidate_tokens=_token_count(tokenizer, original),
            )
        )
    return uncertain


def _rss_mb() -> float | None:
    try:
        import psutil

        return round(float(psutil.Process().memory_info().rss) / (1024 * 1024), 3)
    except (ImportError, OSError):
        return None


def _gpu_snapshot() -> dict[str, float | None]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"peak_vram_mb": None, "gpu_utilization_percent": None}
        return {
            "peak_vram_mb": round(
                max(torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved())
                / (1024 * 1024),
                3,
            ),
            "gpu_utilization_percent": None,
        }
    except (ImportError, AttributeError, RuntimeError):
        return {"peak_vram_mb": None, "gpu_utilization_percent": None}


def _process_start_ms() -> float:
    started = perf_counter()
    subprocess.run(
        [sys.executable, "-c", "pass"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return round((perf_counter() - started) * 1000, 3)


def _payload(case: RuntimeCase) -> dict[str, object]:
    return {
        "original_text": case.original,
        "candidate_text": case.candidate,
        "language": case.language,
        "profile": case.domain,
        "policy": "strict",
    }


def _direct_call(
    guard: ContextGuard, case: RuntimeCase, semantic: Any | None = None
) -> ValidationResult:
    if semantic is None:
        return guard.validate(case.original, case.candidate)
    return guard.validate_with_semantic(case.original, case.candidate, semantic)


def _threaded_calls(
    call: Callable[[], ValidationResult], total: int, concurrency: int
) -> list[dict[str, object]]:
    def timed() -> dict[str, object]:
        started = perf_counter()
        try:
            result = call()
            return {
                "status": result.status.value,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "error": None,
            }
        except Exception as exc:  # benchmark must record failures, not hide them
            return {
                "status": "ERROR",
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "error": type(exc).__name__,
            }

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        return list(executor.map(lambda _: timed(), range(total)))


def _aggregate(
    mode: str,
    phase: str,
    case: RuntimeCase,
    concurrency: int,
    rows: list[dict[str, object]],
    elapsed_ms: float,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    latencies = [float(row["latency_ms"]) for row in rows]
    errors = sum(row["error"] is not None for row in rows)
    return {
        "mode": mode,
        "phase": phase,
        "case_id": case.case_id,
        "bucket": case.bucket,
        "language": case.language,
        "domain": case.domain,
        "actual_character_count": len(case.original),
        "actual_original_tokens": case.original_tokens,
        "actual_candidate_tokens": case.candidate_tokens,
        "concurrency": concurrency,
        "sample_count": len(rows),
        "requests_per_second": round(len(rows) / (elapsed_ms / 1000), 3)
        if elapsed_ms > 0
        else 0.0,
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
        "error_rate": round(errors / len(rows), 6) if rows else 0.0,
        "timeout_rate": 0.0,
        "peak_ram_mb": _rss_mb(),
        **_gpu_snapshot(),
        **(metadata or {}),
    }


def _run_direct_modes(
    cases: list[RuntimeCase],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metrics: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    for case in cases:
        guard = ContextGuard(GuardConfig(language=case.language, profile=case.domain))
        cold_started = perf_counter()
        cold_result = guard.validate(case.original, case.candidate)
        cold_ms = round((perf_counter() - cold_started) * 1000, 3)
        metrics.append(
            _aggregate(
                "R1_direct_deterministic",
                "cold",
                case,
                1,
                [{"status": cold_result.status.value, "latency_ms": cold_ms, "error": None}],
                cold_ms,
                {"process_start_ms": _process_start_ms(), "first_request_ms": cold_ms},
            )
        )
        for concurrency in DETERMINISTIC_CONCURRENCY:
            started = perf_counter()
            rows = _threaded_calls(
                lambda guard=guard, case=case: guard.validate(case.original, case.candidate),
                total=max(20, concurrency * 4),
                concurrency=concurrency,
            )
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            metrics.append(
                _aggregate(
                    "R1_direct_deterministic",
                    "warm",
                    case,
                    concurrency,
                    rows,
                    elapsed_ms,
                    {"process_start_ms": None, "first_request_ms": None},
                )
            )
            samples.extend(
                {"mode": "R1_direct_deterministic", "phase": "warm", **row} for row in rows
            )
    return metrics, samples


async def _asgi_calls(case: RuntimeCase, total: int, concurrency: int) -> list[dict[str, object]]:
    transport = httpx.ASGITransport(app=create_app())
    limits = httpx.Limits(max_connections=concurrency)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://asgi", limits=limits
    ) as client:
        semaphore = asyncio.Semaphore(concurrency)

        async def one() -> dict[str, object]:
            async with semaphore:
                started = perf_counter()
                try:
                    response = await client.post("/v1/validate", json=_payload(case))
                    response.raise_for_status()
                    body = response.json()
                    return {
                        "status": str(body["status"]),
                        "latency_ms": round((perf_counter() - started) * 1000, 3),
                        "error": None,
                    }
                except Exception as exc:  # benchmark must record failures
                    return {
                        "status": "ERROR",
                        "latency_ms": round((perf_counter() - started) * 1000, 3),
                        "error": type(exc).__name__,
                    }

        return list(await asyncio.gather(*(one() for _ in range(total))))


def _run_asgi(cases: list[RuntimeCase]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metrics: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    for case in cases:
        cold_started = perf_counter()
        cold_rows = asyncio.run(_asgi_calls(case, 1, 1))
        cold_ms = round((perf_counter() - cold_started) * 1000, 3)
        metrics.append(
            _aggregate(
                "R2_asgi_in_process_deterministic",
                "cold",
                case,
                1,
                cold_rows,
                cold_ms,
                {"process_start_ms": None, "first_request_ms": cold_ms},
            )
        )
        for concurrency in DETERMINISTIC_CONCURRENCY:
            started = perf_counter()
            rows = asyncio.run(_asgi_calls(case, max(20, concurrency * 4), concurrency))
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            metrics.append(
                _aggregate(
                    "R2_asgi_in_process_deterministic",
                    "warm",
                    case,
                    concurrency,
                    rows,
                    elapsed_ms,
                    {"process_start_ms": None, "first_request_ms": None},
                )
            )
            samples.extend(
                {"mode": "R2_asgi_in_process_deterministic", "phase": "warm", **row}
                for row in rows
            )
    return metrics, samples


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http(url: str, timeout_s: float = 45.0) -> float:
    started = perf_counter()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                return round((perf_counter() - started) * 1000, 3)
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise TimeoutError(f"service did not become healthy: {url}")


def _http_calls(
    url: str, case: RuntimeCase, total: int, concurrency: int
) -> list[dict[str, object]]:
    def call() -> ValidationResult:
        response = httpx.post(url, json=_payload(case), timeout=30.0)
        response.raise_for_status()
        body = response.json()
        return ValidationResult.model_validate(body)

    return _threaded_calls(call, total=total, concurrency=concurrency)


def _run_service_mode(
    mode: str,
    cases: list[RuntimeCase],
    command: list[str],
    url_host: str,
    cleanup: Callable[[], None],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metrics: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        health_ms = _wait_http(f"{url_host}/v1/health")
        for case in cases:
            first_started = perf_counter()
            first_rows = _http_calls(f"{url_host}/v1/validate", case, 1, 1)
            first_ms = round((perf_counter() - first_started) * 1000, 3)
            metrics.append(
                _aggregate(
                    mode,
                    "cold",
                    case,
                    1,
                    first_rows,
                    first_ms,
                    {"process_start_ms": health_ms, "first_request_ms": first_ms},
                )
            )
            for concurrency in DETERMINISTIC_CONCURRENCY:
                started = perf_counter()
                rows = _http_calls(
                    f"{url_host}/v1/validate", case, max(20, concurrency * 4), concurrency
                )
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                metrics.append(
                    _aggregate(
                        mode,
                        "warm",
                        case,
                        concurrency,
                        rows,
                        elapsed_ms,
                        {"process_start_ms": None, "first_request_ms": None},
                    )
                )
                samples.extend({"mode": mode, "phase": "warm", **row} for row in rows)
    finally:
        cleanup()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    return metrics, samples


def _run_localhost(
    cases: list[RuntimeCase],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    port = _find_free_port()
    return _run_service_mode(
        "R3_localhost_http_deterministic",
        cases,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "context_guard.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        f"http://127.0.0.1:{port}",
        lambda: None,
    )


def _run_docker(
    cases: list[RuntimeCase], image: str
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    subprocess.run(["docker", "build", "--tag", image, "."], check=True, timeout=600)
    port = _find_free_port()
    container = f"contextguard-runtime-{os.getpid()}"
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--detach",
            "--name",
            container,
            "--publish",
            f"{port}:8000",
            image,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    def cleanup() -> None:
        subprocess.run(["docker", "rm", "--force", container], check=False, capture_output=True)

    return _run_service_mode(
        "R4_docker_http_deterministic",
        cases,
        [sys.executable, "-c", "pass"],
        f"http://127.0.0.1:{port}",
        cleanup,
    )


def _run_hybrid(
    cases: list[RuntimeCase],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metrics: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    verifier = TransformersSemanticVerifier(device="auto", local_files_only=True)
    load_started = perf_counter()
    verifier._load()
    model_load_ms = round((perf_counter() - load_started) * 1000, 3)
    for case in cases:
        guard = ContextGuard(GuardConfig(language=case.language, profile=case.domain))
        first_started = perf_counter()
        first_result = _direct_call(guard, case, verifier)
        first_ms = round((perf_counter() - first_started) * 1000, 3)
        metrics.append(
            _aggregate(
                "R5_direct_hybrid_semantic",
                "cold",
                case,
                1,
                [{"status": first_result.status.value, "latency_ms": first_ms, "error": None}],
                first_ms,
                {
                    "process_start_ms": _process_start_ms(),
                    "model_load_ms": model_load_ms,
                    "first_request_ms": first_ms,
                    "semantic_model_id": getattr(verifier, "model_id", None),
                    "semantic_model_revision": getattr(verifier, "model_revision", None),
                },
            )
        )
        for concurrency in SEMANTIC_CONCURRENCY:
            started = perf_counter()
            rows = _threaded_calls(
                lambda guard=guard, case=case: _direct_call(guard, case, verifier),
                total=max(2, concurrency),
                concurrency=concurrency,
            )
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            metrics.append(
                _aggregate(
                    "R5_direct_hybrid_semantic",
                    "warm",
                    case,
                    concurrency,
                    rows,
                    elapsed_ms,
                    {
                        "process_start_ms": None,
                        "model_load_ms": None,
                        "first_request_ms": None,
                        "semantic_model_id": getattr(verifier, "model_id", None),
                        "semantic_model_revision": getattr(verifier, "model_revision", None),
                    },
                )
            )
            samples.extend(
                {"mode": "R5_direct_hybrid_semantic", "phase": "warm", **row}
                for row in rows
            )
    return metrics, samples


def _write_artifacts(
    output: Path,
    metrics: list[dict[str, object]],
    samples: list[dict[str, object]],
    cases: list[RuntimeCase],
    *,
    include_docker: bool,
    hybrid_case_ids: list[str],
    skipped_hybrid_cases: list[dict[str, object]],
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    direct_baselines = {
        (
            str(row["case_id"]),
            str(row["bucket"]),
            str(row["language"]),
            str(row["concurrency"]),
        ): float(row["p50_ms"])
        for row in metrics
        if row["mode"] == "R1_direct_deterministic"
        and row["phase"] == "warm"
        and all(key in row for key in ("case_id", "bucket", "language", "concurrency", "p50_ms"))
    }
    for row in metrics:
        if not all(
            key in row for key in ("case_id", "bucket", "language", "concurrency", "p50_ms")
        ):
            row.setdefault("api_overhead_ms", None)
            row.setdefault("api_overhead_ratio", None)
            continue
        key = (
            str(row["case_id"]),
            str(row["bucket"]),
            str(row["language"]),
            str(row["concurrency"]),
        )
        baseline = direct_baselines.get(key)
        if baseline is not None and str(row["mode"]).startswith(("R2_", "R3_", "R4_")):
            row["api_overhead_ms"] = round(float(row["p50_ms"]) - baseline, 3)
            row["api_overhead_ratio"] = (
                round(float(row["p50_ms"]) / baseline, 6) if baseline else None
            )
        else:
            row.setdefault("api_overhead_ms", None)
            row.setdefault("api_overhead_ratio", None)
    fieldnames = sorted({key for row in metrics for key in row})
    with (output / "runtime_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(metrics)
    with (output / "runtime_samples.jsonl").open("w", encoding="utf-8") as handle:
        for row in samples:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest: dict[str, object] = {
        "run_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "scope": "M10a",
        "status": "metric_only",
        "modes": sorted({str(row["mode"]) for row in metrics}),
        "docker_included": include_docker,
        "bucket_targets_tokens": BUCKET_TARGETS,
        "cases": [asdict(case) for case in cases],
        "hybrid_case_ids": hybrid_case_ids,
        "skipped_hybrid_cases": skipped_hybrid_cases,
        "semantic_input_limit_tokens": 512,
        "tokenizer_model_id": TOKENIZER_MODEL_ID,
        "tokenizer_revision": TOKENIZER_REVISION,
        "dataset_sha256": _sha256_texts(cases),
        "python_version": sys.version,
        "platform": platform.platform(),
        "git_commit": _git_commit(),
        "config": {
            "deterministic_concurrency": list(DETERMINISTIC_CONCURRENCY),
            "semantic_concurrency": list(SEMANTIC_CONCURRENCY),
            "deterministic_samples_per_level": "max(20, concurrency * 4)",
            "semantic_samples_per_level": "max(2, concurrency)",
            "semantic_model_reused": True,
        },
        "artifacts": ["runtime_manifest.json", "runtime_metrics.csv", "runtime_samples.jsonl"],
    }
    (output / "runtime_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def validate_runtime_artifacts(output: Path) -> dict[str, object]:
    """Validate the M10a artifact contract without rerunning the benchmark."""

    required = ["runtime_manifest.json", "runtime_metrics.csv", "runtime_samples.jsonl"]
    missing = [name for name in required if not (output / name).is_file()]
    if missing:
        raise ValueError(f"missing runtime artifacts: {missing}")
    manifest = json.loads((output / "runtime_manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((output / "runtime_metrics.csv").open(encoding="utf-8")))
    sample_count = sum(1 for _ in (output / "runtime_samples.jsonl").open(encoding="utf-8"))
    expected = {
        "R1_direct_deterministic",
        "R2_asgi_in_process_deterministic",
        "R3_localhost_http_deterministic",
        "R5_direct_hybrid_semantic",
    }
    if manifest.get("docker_included"):
        expected.add("R4_docker_http_deterministic")
    modes = set(str(mode) for mode in manifest.get("modes", []))
    if modes != expected:
        raise ValueError(f"runtime mode mismatch: expected {sorted(expected)}, got {sorted(modes)}")
    if not rows or sample_count <= 0:
        raise ValueError("runtime artifacts contain no measurements")
    if any(float(row["error_rate"]) > 0 or float(row["timeout_rate"]) > 0 for row in rows):
        raise ValueError("runtime artifact contains request errors or timeouts")
    if set(row["bucket"] for row in rows) != set(BUCKET_TARGETS):
        raise ValueError("runtime artifact is missing an input length bucket")
    if any(int(float(row["actual_original_tokens"])) <= 0 for row in rows):
        raise ValueError("runtime artifact has invalid token counts")
    return {
        "valid": True,
        "scope": manifest.get("scope"),
        "modes": sorted(modes),
        "metric_rows": len(rows),
        "sample_rows": sample_count,
        "dataset_sha256": manifest.get("dataset_sha256"),
        "semantic_skips": len(manifest.get("skipped_hybrid_cases", [])),
    }


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run(
    output: Path, *, local_files_only: bool = False, include_docker: bool = True
) -> dict[str, object]:
    tokenizer = _load_tokenizer(local_files_only=local_files_only)
    cases = build_runtime_cases(tokenizer)
    all_uncertain_cases = build_uncertain_cases(cases, tokenizer)
    # The NLI adapter receives original and candidate as a pair. Keeping each
    # side at <=256 tokens prevents the pair from exceeding the model's 512-token
    # input limit; longer buckets remain in deterministic/API measurements and
    # are recorded as explicit semantic skips.
    uncertain_cases = [case for case in all_uncertain_cases if case.original_tokens <= 256]
    skipped_hybrid_cases = [
        {
            "case_id": case.case_id,
            "bucket": case.bucket,
            "original_tokens": case.original_tokens,
            "reason": "MODEL_PAIR_MAX_LENGTH_512",
        }
        for case in all_uncertain_cases
        if case.original_tokens > 512
    ]
    metrics: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    for runner, runner_cases in (
        (_run_direct_modes, cases),
        (_run_asgi, cases),
        (_run_localhost, cases),
        (_run_hybrid, uncertain_cases),
    ):
        mode_metrics, mode_samples = runner(runner_cases)
        metrics.extend(mode_metrics)
        samples.extend(mode_samples)
    if include_docker:
        docker_metrics, docker_samples = _run_docker(cases, "contextguard:runtime")
        metrics.extend(docker_metrics)
        samples.extend(docker_samples)
    return _write_artifacts(
        output,
        metrics,
        samples,
        cases,
        include_docker=include_docker,
        hybrid_case_ids=[case.case_id for case in uncertain_cases],
        skipped_hybrid_cases=skipped_hybrid_cases,
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".runtime/runtime_m10"))
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--validate-artifacts", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_artifacts:
        print(json.dumps(validate_runtime_artifacts(args.output), ensure_ascii=False, indent=2))
        return 0
    manifest = run(
        args.output,
        local_files_only=args.local_files_only,
        include_docker=not args.skip_docker,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
