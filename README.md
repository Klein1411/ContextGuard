# ContextGuard

ContextGuard kiểm tra candidate text sau khi nén có làm mất hoặc đảo các dữ kiện quan trọng so với original text hay không. Core chạy offline, ưu tiên phát hiện lỗi critical và trả `PASS`, `FAIL`, hoặc `UNCERTAIN`.

## Installation

Yêu cầu Python 3.11 và `uv`:

```powershell
uv sync --group dev
```

## Quick start

```python
from context_guard import ContextGuard, GuardConfig

guard = ContextGuard(GuardConfig(language="vi", profile="technical", policy="strict"))
result = guard.validate(
    original_text="Không triển khai nếu accuracy thấp hơn 90%.",
    candidate_text="Triển khai nếu accuracy thấp hơn 90%.",
)
print(result.status, result.recommended_action)
```

## REST API

```powershell
uv run context-guard serve
```

Routes V1: `/v1/health`, `/v1/capabilities`, `/v1/analyze`, `/v1/validate`. OpenAPI is available at `/docs`.

## Profiles and policies

Profiles are `general`, `academic`, `business`, and `technical`. Policies are `lenient`, `balanced`, and `strict`; strict is the default and falls back to the original text for `FAIL` or `UNCERTAIN`.

## CLI

```text
context-guard analyze
context-guard validate
context-guard serve
context-guard benchmark
context-guard clean
context-guard capabilities
```

Commands accept arguments, text files, or stdin as documented by `--help`.

## Tests and benchmark

```powershell
uv run pytest
uv run ruff check .
uv run mypy src
uv run context-guard benchmark --output .runtime/benchmark --dataset benchmarks/datasets/golden_v0_provisional.jsonl
uv run context-guard benchmark --output .runtime/benchmark --validate-artifacts
```

Verified local provisional runs on 2026-07-29 (seed `20260729`) report Tier A 300 samples and Tier B 2,014 samples; both had false acceptance `0.0`, unsafe detection recall `1.0`, false rejection `0.0`, and precision `1.0`. Rules-only P95 latency was 0.533 ms (Tier A) and 1.891 ms (Tier B) in the post-commit runs. The datasets are synthetic/unverified, so these numbers are not a manual golden-set, compressor, or paper-grade claim. Use `--validate-artifacts` before any retention; promotion is guarded and refuses unverified labels.

## What it does not do

The core does not read PDF/DOCX/PPTX/images/audio/websites, call external services, store requests, or provide a React product UI. External repositories should convert documents to text before calling ContextGuard.

## Limitations and roadmap

Deterministic checks are strongest for explicit numbers, units, versions, technical literals, negation, thresholds, conditions, and exceptions. Ambiguous or unsupported semantics return `UNCERTAIN`. Future work is tracked in `CONTEXT.md`.
