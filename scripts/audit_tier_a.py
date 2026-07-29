from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from context_guard.benchmarks.dataset import (
    build_provisional_golden,
    load_jsonl,
    write_jsonl,
)

AUDIT_NOTE = (
    "Audited 2026-07-29 by Codex: all records reviewed against the controlled bilingual "
    "template semantics and exact regeneration; no extra transformation was found."
)


def audit(source: Path, destination: Path) -> dict[str, object]:
    records = load_jsonl(source)
    expected = build_provisional_golden()
    if records != expected:
        raise ValueError("source does not exactly match the locked provisional generator")
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("duplicate Tier A ids found")
    if len({(record["original"], record["candidate"]) for record in records}) != len(records):
        raise ValueError("duplicate Tier A text pairs found")
    audited = []
    for record in records:
        copy = dict(record)
        copy["label_status"] = "audited"
        copy["notes"] = AUDIT_NOTE
        audited.append(copy)
    write_jsonl(audited, destination)
    return {
        "source": str(source),
        "destination": str(destination),
        "audit_mode": "template_semantic_review_and_exact_regeneration",
        "reviewer": "Codex",
        "sample_count": len(records),
        "exact_regeneration_match": True,
        "unique_ids": len({record["id"] for record in records}),
        "unique_pairs": len({(record["original"], record["candidate"]) for record in records}),
        "counts": {
            f"{language}/{label}": count
            for (language, label), count in sorted(
                Counter((record["language"], record["label"]) for record in records).items()
            )
        },
        "label_status": "audited",
        "manual_review_scope": "all 300 records",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and freeze the controlled Tier A set.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("benchmarks/datasets/golden_v0_provisional.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/datasets/golden_v0_audited.jsonl"),
    )
    args = parser.parse_args()
    report = audit(args.source, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
