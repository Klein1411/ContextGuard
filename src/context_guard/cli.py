from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from context_guard import ContextGuard, GuardConfig
from context_guard.adapters import RuleBasedCompressor
from context_guard.benchmarks.candidates import (
    build_unverified_candidates,
    validate_candidates,
    write_candidates,
)
from context_guard.benchmarks.dataset import load_jsonl
from context_guard.benchmarks.runner import promote_run, run_benchmark, validate_run_artifacts


def _text(value: str | None, filename: str | None) -> str:
    if filename:
        return Path(filename).read_text(encoding="utf-8")
    if value is not None:
        return value
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="context-guard")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("text", nargs="?")
    analyze.add_argument("--file")
    analyze.add_argument("--language", default="auto")
    analyze.add_argument("--profile", default="general")
    validate = sub.add_parser("validate")
    validate.add_argument("original", nargs="?")
    validate.add_argument("candidate", nargs="?")
    validate.add_argument("--original-file")
    validate.add_argument("--candidate-file")
    validate.add_argument("--language", default="auto")
    validate.add_argument("--profile", default="general")
    validate.add_argument("--policy", default="strict")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--output", default=".runtime/benchmark")
    benchmark.add_argument("--seed", type=int, default=20260729)
    benchmark.add_argument("--dataset", default="benchmarks/datasets/golden_v0_provisional.jsonl")
    benchmark.add_argument("--validate-artifacts", action="store_true")
    benchmark.add_argument("--promote-final", action="store_true")
    candidates = sub.add_parser("candidates")
    candidates.add_argument("--source", default="benchmarks/datasets/golden_v0_provisional.jsonl")
    candidates.add_argument("--output", default=".runtime/tier_c_rule_based_unverified.jsonl")
    candidates.add_argument("--adapter", choices=["rule-based"], default="rule-based")
    sub.add_parser("capabilities")
    clean = sub.add_parser("clean")
    clean.add_argument("--runtime", default=".runtime")
    args = parser.parse_args(argv)
    if args.command == "analyze":
        print(
            ContextGuard(GuardConfig(language=args.language, profile=args.profile))
            .analyze(_text(args.text, args.file))
            .model_dump_json(indent=2, ensure_ascii=False)
        )
    elif args.command == "validate":
        original = _text(args.original, args.original_file)
        candidate = _text(args.candidate, args.candidate_file)
        print(
            ContextGuard(
                GuardConfig(language=args.language, profile=args.profile, policy=args.policy)
            )
            .validate(original, candidate)
            .model_dump_json(indent=2, ensure_ascii=False)
        )
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("context_guard.api.app:app", host=args.host, port=args.port)
    elif args.command == "benchmark":
        output = Path(args.output)
        if args.validate_artifacts:
            payload = validate_run_artifacts(output)
        elif args.promote_final:
            payload = promote_run(output)
        else:
            payload = run_benchmark(output, args.seed, Path(args.dataset))
        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "candidates":
        source = load_jsonl(Path(args.source))
        compressor = RuleBasedCompressor()
        records = build_unverified_candidates(source, compressor)
        write_candidates(records, Path(args.output))
        print(json.dumps(validate_candidates(records), ensure_ascii=False, indent=2))
    elif args.command == "capabilities":
        print(
            json.dumps(
                {
                    "languages": ["vi", "en", "auto"],
                    "profiles": ["general", "academic", "business", "technical"],
                    "policies": ["lenient", "balanced", "strict"],
                    "validators": ["ExactGuard", "LogicGuard", "EntityGuard", "RelationGuard"],
                    "semantic_verifier_available": False,
                    "compressor_adapters": [
                        "rule-based",
                        "controlled-mutation",
                        "llmlingua-2-optional",
                        "token-level-unavailable",
                        "llm-summarizer-unavailable",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "clean":
        target = Path(args.runtime)
        if target.is_dir():
            shutil.rmtree(target)
        print(f"Cleaned {target}")
    return 0
