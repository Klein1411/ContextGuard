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
- M5 benchmark: Tier A (300) and Tier B (2,001) datasets, deterministic runner, per-category metrics, reproducibility signature, artifact validation, and guarded promotion helper implemented. Tier A was audited and frozen; Tier B remains synthetic/unverified.
- M6 compressor adapters: rule-based protected-span compressor, controlled mutations, Tier C unverified candidate generation, and a lazy revision-pinned LLMLingua-2 adapter implemented and exercised; the LLM summarizer remains an explicit unavailable boundary.
- M7 semantic verifier: optional only-on-UNCERTAIN orchestration, safe unavailable/error fallback, and a lazy revision-pinned Transformers NLI adapter implemented. A CPU smoke and an uncertainty-path benchmark succeeded; quality benchmarking remains provisional.
- M8 packaging: package, CLI, FastAPI, non-root Dockerfile, health check, local image build, and container smoke test completed.
- M9 final audit: deterministic gates, Tier A audit, dependency/security checks, real adapter measurements, resource measurements, and audited Tier A artifact promotion completed; optional quality expansion remains limited.

# Current Status

Status: `COMPLETED_WITH_LIMITATIONS` (audited deterministic Tier A artifact is promoted; Tier B, real compressor outputs, and hybrid semantic measurements remain bounded/unverified).

Repository was empty at start. Environment audit: Windows 11, i5-12500H, 24 GB RAM, RTX 3050 Laptop 4 GB, Python 3.11 available, `uv` and Git available. No model or cache is in the repository.

# Completed Work

Repository foundation, public schemas, FastAPI V1 routes, CLI, ExactGuard, LogicGuard, EntityGuard, RelationGuard, risk/policy mapping, protected-span rule-based compressor, controlled mutation adapter, Tier C candidate generator, optional adapter boundaries, semantic fallback orchestration, and tests are implemented.

# Verified Results

Verified on 2026-07-29 with Python 3.11.9: 51 pytest tests pass; Ruff check passes; mypy passes on 33 source files; package build and clean-wheel install smoke test succeed; coverage run reports 79% line coverage (no minimum threshold is claimed). On code commit `77e2c38` with seed 20260729, Tier A `golden_v0_provisional` produced 300 samples (150 SAFE, 150 UNSAFE) with exactly 75 samples per domain: false acceptance 0.0, unsafe detection recall 1.0, false rejection 0.0, precision 1.0, P50/P95 0.362/0.604 ms, peak RAM 30.414 MB, peak VRAM not measured. Tier B `mutation_v0_provisional` produced 2,001 samples (218 SAFE, 1,783 UNSAFE), including 109 safe date-format transformations and 109 safe identity records: false acceptance 0.0, unsafe detection recall 1.0, false rejection 0.0, precision 1.0, P50/P95 1.305/2.224 ms, peak RAM 38.375 MB, peak VRAM not measured. Both runs passed the runner's metric-only quality gate (recall ≥95%, FAR ≤2%, P95 ≤50 ms); manual-label and contract/regression gates remain separate. ExactGuard regression coverage now includes duplicated, added, and newly introduced fact-type literals; relation coverage now includes metric-dataset, config-component, and method-dataset changes; LogicGuard now rejects changed condition/exception markers. Tier C generation produced 300 rule-based candidates with `label_status=unverified` and valid UTF-8; no quality metric was assigned. A bounded real LLMLingua-2 run on 20 provisional samples completed with model `microsoft/llmlingua-2-xlm-roberta-large-meetingbank@ebaba9b`, mean compression time 1,501.630 ms, RSS about 1,984.902 MB, and all outputs explicitly marked `unverified`; no quality metric or promotion was assigned. Repeated Tier A runs produced the same `decision_sha256`; elapsed time and per-sample latency are expected to vary. Docker image `contextguard:local` also built successfully and a non-root container returned HTTP 200 from `/v1/health`; `/v1/capabilities` and `/v1/validate` smoke checks passed. The reusable `run_hybrid_benchmark` API was exercised on 20 `UNCERTAIN` identity cases: deterministic false rejection was 1.0, hybrid false rejection was 0.0, semantic calls were 20/20, P50/P95 98.695/102.872 ms, peak RSS 1,481.086 MB, and peak VRAM was not measured. The 300/2,001 provisional sets had no `UNCERTAIN` cases, so they did not call the semantic adapter. These are adapter/resource measurements, not hybrid quality claims. These are synthetic/unverified results, not a manual golden-set or paper-grade quality claim.

GPU follow-up: a separate external CUDA venv using `torch 2.8.0+cu126` detected the RTX 3050 and ran the same 20-case uncertainty-path benchmark on CUDA. It called the semantic adapter 20/20 times, returned 20/20 `PASS`, measured P50/P95 17.087/117.275 ms, peak RSS 2,625.801 MB, and peak allocated/reserved VRAM 1,120.0 MB of 4,095.5 MB. This remains a metric-only, synthetic/unverified behavior/resource smoke, not a hybrid quality gate; the repository's default venv remains CPU-only.

Mixed semantic smoke: 20 deliberately uncertain cases (16 controlled unsafe paraphrases and 4 safe identities) on the same CUDA environment produced hybrid false acceptance 0.0, unsafe detection recall 1.0, false rejection 0.0, precision 1.0, fallback rate 0.2, P50/P95 21.862/310.104 ms, peak RSS 2,619.078 MB, and peak VRAM 1,120.0 MB. All labels remain `synthetic_unverified`; this is not a golden-set or production quality claim.

Tier A audit regenerated the dataset exactly (`300/300` records), reviewed all records against the controlled bilingual template semantics, found 300 unique IDs and pairs, balanced `75` per language/label cell, and confirmed the expected mutation counts. The audited copy is `benchmarks/datasets/golden_v0_audited.jsonl` with `label_status=audited`; the audit reviewer is Codex, not an external domain expert.

Final audit evidence: `pip-audit --local` reported no known vulnerabilities; tracked secret, large-file, forbidden-path, and model-weight scans were clean.

# Known Limitations

- Deterministic V1 cannot prove unrestricted natural-language equivalence.
- Entity and relation handling will be conservative and may return `UNCERTAIN`.
- Tier A is audited against controlled templates, but not independently reviewed by an external domain expert. Tier B mutations remain controlled synthetic records; claims outside the audited deterministic set remain provisional.
- Real token compressor quality and production end-to-end token savings are not yet measured. The LLMLingua-2 smoke produced candidates but showed high CPU/RAM cost and is explicitly unverified; a 20-case run is not a quality gate.
- Hybrid semantic quality is not yet established: both CPU and CUDA 20-case uncertainty-path runs are resource/behavior smokes only, and the full provisional sets had no uncertain cases. The default project venv remains CPU-only; the external CUDA measurement is recorded above and is not a production resource guarantee.
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

Next: expand the externally reviewed golden set, add a larger labelled hybrid semantic benchmark, and measure end-to-end token savings before making production or paper-grade claims. Do not promote synthetic or unverified runs to `artifacts/final/`; `promote_run` requires `label_status` `verified` or `audited` and a validated artifact set.
