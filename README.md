# ContextGuard

ContextGuard kiểm tra candidate text sau khi nén có làm mất hoặc đảo các dữ kiện quan trọng so với original text hay không. Core chạy offline, ưu tiên phát hiện lỗi critical và trả `PASS`, `FAIL`, hoặc `UNCERTAIN`.

## Installation

Yêu cầu Python 3.11 và `uv`:

```powershell
uv sync --group dev
```

Để benchmark đo peak RAM, cài thêm nhóm tùy chọn: `uv sync --group benchmark`.
Để cài toàn bộ adapter tùy chọn: `uv sync --group all`.

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

## Python API

`ContextGuard`, `GuardConfig`, `AnalyzeResult`, `ValidationResult`, `Fact`, `ProtectedSpan`,
`Violation`, `SafetyStatus`, `RiskLevel`, and `RecommendedAction` được export trực tiếp từ
`context_guard`. Core chỉ chạy deterministic/offline; semantic verifier là adapter opt-in.

## REST API

```powershell
uv run context-guard serve
```

Routes V1: `/v1/health`, `/v1/capabilities`, `/v1/analyze`, `/v1/validate`. OpenAPI is available at `/docs`.

## Profiles and policies

Profiles are `general`, `academic`, `business`, and `technical`. Policies are `lenient`, `balanced`, and `strict`; strict is the default and falls back to the original text for `FAIL` or `UNCERTAIN`.

The adapter boundary includes `RuleBasedCompressor`, controlled mutations, a lazy `LLMLingua2Compressor`, and an explicit unavailable placeholder for LLM summarizer backends. `ContextGuard.validate_with_semantic(...)` invokes a semantic verifier only for deterministic `UNCERTAIN`; adapter errors keep the safe fallback. LLMLingua-2 remains opt-in and unverified until a real Tier C run is manually audited.

Semantic adapter tùy chọn dùng `TransformersSemanticVerifier` với model multilingual
`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, revision `add259b`, license MIT. Cài bằng
`uv sync --group semantic`; model tải vào cache ngoài repository, CPU fallback hoạt động khi
CUDA không khả dụng. Smoke test local đã chạy được trên CPU; chưa dùng kết quả này làm quality
gate hybrid.

## CLI

```text
context-guard analyze
context-guard validate
context-guard serve
context-guard benchmark
context-guard candidates
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
uv run context-guard candidates --output .runtime/tier_c_rule_based_unverified.jsonl
```

Docker smoke test (requires Docker Desktop):

```powershell
docker build --tag contextguard:local .
docker run --rm -p 8000:8000 contextguard:local
```

The local image was built and a non-root container was smoke-tested on 2026-07-29: `/v1/health` returned `200`, `/v1/capabilities` reported the expected adapter boundary, and `/v1/validate` returned `FAIL` for a Python 3.11 versus 3.12 version change. The image is not published.

Verified local provisional runs on 2026-07-29 (code commit `c4ff25e`, seed `20260729`) report Tier A 300 samples and Tier B 2,001 samples; both had false acceptance `0.0`, unsafe detection recall `1.0`, false rejection `0.0`, and precision `1.0`. Tier A is exactly balanced across the four domains. Tier B includes real safe date-format transformations in addition to identity records. Rules-only P50/P95 latency was 0.386/0.659 ms (Tier A) and 1.248/2.215 ms (Tier B); measured peak RAM was 30.281 MB and 38.426 MB respectively, while peak VRAM was not measured. The datasets are synthetic/unverified, so these numbers are not a manual golden-set, compressor, or paper-grade claim. Use `--validate-artifacts` before any retention; promotion is guarded and refuses unverified labels.

`candidates` generates Tier C rule-based candidates with `label_status=unverified`; it never assigns correctness labels automatically.

## What it does not do

The core does not read PDF/DOCX/PPTX/images/audio/websites, call external services, store requests, or provide a React product UI. External repositories should convert documents to text before calling ContextGuard.

## Limitations and roadmap

Deterministic checks are strongest for explicit numbers, units, versions, technical literals, negation, thresholds, conditions, and exceptions. Ambiguous or unsupported semantics return `UNCERTAIN`. Future work is tracked in `CONTEXT.md`.
