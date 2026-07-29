from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from context_guard import ContextGuard, GuardConfig
from context_guard.benchmarks.runner import run_benchmark


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
    benchmark.add_argument("--output", default="artifacts/final")
    benchmark.add_argument("--seed", type=int, default=20260729)
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
        print(json.dumps(run_benchmark(Path(args.output), args.seed), ensure_ascii=False, indent=2))
    elif args.command == "capabilities":
        print(
            json.dumps(
                {
                    "languages": ["vi", "en", "auto"],
                    "profiles": ["general", "academic", "business", "technical"],
                    "policies": ["lenient", "balanced", "strict"],
                    "validators": ["ExactGuard", "LogicGuard", "EntityGuard", "RelationGuard"],
                    "semantic_verifier_available": False,
                    "compressor_adapters": [],
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
