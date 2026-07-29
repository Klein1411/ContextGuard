# Project Identity

ContextGuard is an offline-first Python package and FastAPI service that checks whether compressed text preserves critical facts and logic from the original text. Repository root: `D:\fact_safeguard`.

# Locked Scope

- Core input is text only: `original_text` and `candidate_text`.
- Languages: Vietnamese and English, with `vi`, `en`, and `auto` modes.
- Profiles: `general`, `academic`, `business`, `technical`.
- Policies: `lenient`, `balanced`, `strict`; strict is the default.
- Safety statuses: `PASS`, `FAIL`, `UNCERTAIN`.
- Core is deterministic and offline. Compressors and semantic verifiers are adapters.
- No React UI, document readers, cache service, telemetry, or remote calls in core.
- Exactly three Markdown files are allowed; this file is the living project context.

# Architecture

`ContextGuard` orchestrates normalization, extraction, deterministic validators, policy mapping, scoring, and reporting. FastAPI routes use the same Pydantic schemas as the Python API. Compressor adapters consume `ProtectedSpan` data optionally and return text candidates; the core never imports a compressor.

Initial implementation uses dependency-light regular expressions and conservative evidence rules. Ambiguous locale, unsupported relation structures, and unavailable optional adapters produce warnings or `UNCERTAIN` rather than guesses.

# API Contract

V1 routes: `GET /v1/health`, `GET /v1/capabilities`, `POST /v1/analyze`, `POST /v1/validate`. Public enums and response fields are defined in `src/context_guard/schemas/models.py`. Breaking changes require `/v2`.

# Technical Decisions

- Python 3.11 is the target runtime; native Windows is preferred.
- `uv` manages dependencies and the lockfile. Runtime core remains free of ML dependencies.
- Critical deterministic violations use strict fallback to `USE_ORIGINAL`.
- Risk score is a documented weighted maximum/accumulation over violations, clamped to `[0, 1]`.
- Exact matching precedes semantic matching. Semantic verification is deferred and optional.
- Input length is bounded and rejected with a structured error; text is never silently truncated.

# Milestones

- M0 foundation: completed; repository audit is clean and changes are committed.
- M1 schema/API contract: implemented and contract-tested.
- M2 ExactGuard: implemented for explicit numeric, percentage, currency, date/time, unit, version, URL/email, path, flag, and code facts.
- M3 LogicGuard: implemented for bilingual negation, comparisons, conditions, exceptions, and modality.
- M4 relation/entity: conservative explicit-structure implementation added; broad semantic NER remains limited.
- M5 benchmark: provisional Tier A (300) and Tier B (2,001) datasets, deterministic runner, per-category metrics, reproducibility signature, artifact validation, and guarded promotion helper implemented. Both datasets remain synthetic/unverified.
- M6 compressor adapters: rule-based protected-span compressor, controlled mutations, Tier C unverified candidate generation, and a lazy revision-pinned LLMLingua-2 adapter implemented; the LLM summarizer remains an explicit unavailable boundary.
- M7 semantic verifier: optional only-on-UNCERTAIN orchestration, safe unavailable/error fallback, and a lazy revision-pinned Transformers NLI adapter implemented. A CPU smoke run succeeded; hybrid quality benchmarking remains pending.
- M8 packaging: package, CLI, FastAPI, non-root Dockerfile, health check, local image build, and container smoke test completed.
- M9 final audit: pending manual label audit, real compressor/semantic measurements, resource measurements, and final artifact promotion.

# Current Status

Status: `IMPLEMENTATION_COMPLETE_BENCHMARK_PENDING` (provisional synthetic benchmark exists; manual golden and real compressor quality gates are pending).

Repository was empty at start. Environment audit: Windows 11, i5-12500H, 24 GB RAM, RTX 3050 Laptop 4 GB, Python 3.11 available, `uv` and Git available. No model or cache is in the repository.

# Completed Work

Repository foundation, public schemas, FastAPI V1 routes, CLI, ExactGuard, LogicGuard, EntityGuard, RelationGuard, risk/policy mapping, protected-span rule-based compressor, controlled mutation adapter, Tier C candidate generator, optional adapter boundaries, semantic fallback orchestration, and tests are implemented.

# Verified Results

Verified on 2026-07-29 with Python 3.11.9: 49 pytest tests pass; Ruff check passes; mypy passes on 32 source files; package build and clean-wheel install smoke test succeed; coverage run reports 78% line coverage (no minimum threshold is claimed). On code commit `77e2c38` with seed 20260729, Tier A `golden_v0_provisional` produced 300 samples (150 SAFE, 150 UNSAFE) with exactly 75 samples per domain: false acceptance 0.0, unsafe detection recall 1.0, false rejection 0.0, precision 1.0, P50/P95 0.362/0.604 ms, peak RAM 30.414 MB, peak VRAM not measured. Tier B `mutation_v0_provisional` produced 2,001 samples (218 SAFE, 1,783 UNSAFE), including 109 safe date-format transformations and 109 safe identity records: false acceptance 0.0, unsafe detection recall 1.0, false rejection 0.0, precision 1.0, P50/P95 1.305/2.224 ms, peak RAM 38.375 MB, peak VRAM not measured. Both runs passed the runner's metric-only quality gate (recall ≥95%, FAR ≤2%, P95 ≤50 ms); manual-label and contract/regression gates remain separate. ExactGuard regression coverage now includes duplicated, added, and newly introduced fact-type literals; relation coverage now includes metric-dataset, config-component, and method-dataset changes; LogicGuard now rejects changed condition/exception markers. Tier C generation produced 300 rule-based candidates with `label_status=unverified` and valid UTF-8; no quality metric was assigned. Repeated Tier A runs produced the same `decision_sha256`; elapsed time and per-sample latency are expected to vary. Docker image `contextguard:local` also built successfully and a non-root container returned HTTP 200 from `/v1/health`; `/v1/capabilities` and `/v1/validate` smoke checks passed. The optional Transformers NLI adapter loaded model `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli@add259b` on CPU and returned an entailment `PASS` on an identical ambiguous-date pair; warm inference P50/P95 was 91.997/187.474 ms with peak RSS 1,498.480 MB, and peak VRAM was not measured. This is an adapter smoke/resource measurement, not a hybrid quality benchmark. These are synthetic/unverified results, not a manual golden-set or paper-grade quality claim.

Final audit evidence: `pip-audit --local` reported no known vulnerabilities; tracked secret, large-file, forbidden-path, and model-weight scans were clean.

# Known Limitations

- Deterministic V1 cannot prove unrestricted natural-language equivalence.
- Entity and relation handling will be conservative and may return `UNCERTAIN`.
- The required sample counts now exist, but Tier A labels have not been manually audited and Tier B mutations are controlled synthetic records; quality claims remain provisional.
- Real token compressor quality, LLMLingua-2 runtime/resource behavior, hybrid semantic quality, GPU VRAM, and production end-to-end token savings are not yet measured. The optional semantic adapter has only a CPU smoke/resource measurement; rules-only P50/P95 are measured above.
- A bounded LLMLingua-2 CPU smoke attempt exceeded five minutes during model download/initialization and was stopped; no compressor output or quality metric is claimed. Its external cache is outside the repository.
- FastAPI integration test emits an upstream Starlette/httpx deprecation warning; tests still pass.
- Docker image build and non-root container smoke test are verified locally; no registry publication or production deployment has been performed.

# Deferred Improvements

- FastAPI + React product UI after API V1, final benchmark, core quality gate, and separate semantic evaluation.
- Cache as a separate project.
- SmartContext Gateway later.
- CC-DFlash integration later.
- Semantic verifier must not replace the deterministic core.
- PDF/DOCX adapters belong in external repositories.
- Distributed deployment later.

# Repository Hygiene

Temporary files belong in `.runtime/`. Final benchmark artifacts are restricted to `artifacts/final/` and the whitelist in the specification. Models use an external cache and are never copied into Git. Keep source and tests free of generated files.

# Next Action

Next: manually audit and freeze Tier A labels, retry Tier C with a bounded real compressor run only after a resource/timeout decision, then benchmark rules-only versus hybrid semantic behavior and measure VRAM. Do not promote synthetic or unverified runs to `artifacts/final/`; `promote_run` requires `label_status` `verified` or `audited` and a validated artifact set.
