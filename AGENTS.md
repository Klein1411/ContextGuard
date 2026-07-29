# Agent Instructions

Always read `AGENTS.md`, `CONTEXT.md`, and `README.md` before changing the project.

Rules:

- `CONTEXT.md` is the source of truth for scope, progress, decisions, and handoff.
- Keep exactly the three repository Markdown files: `README.md`, `AGENTS.md`, and `CONTEXT.md`.
- Do not create fake metrics, tune on the test set, delete difficult samples, or claim unverified results.
- Keep the deterministic core independent of compressors, caches, remote services, and ML models.
- Optional semantic verification may only run after deterministic validators return `UNCERTAIN` and may never override a clear critical failure.
- Do not break the V1 API contract; use a new API version for breaking changes.
- Put temporary files under `.runtime/`; do not commit models, caches, secrets, logs, or generated build output.
- Do not build a product UI before the core, API, and benchmark gates are stable.
- Run tests, lint, type checks, cleanup, and a repository-status audit at each milestone.
- Prefer UTF-8 Vietnamese documentation and clear English public error codes.
