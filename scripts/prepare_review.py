"""Prepare blind M12 reviewer packets without labels or builder metadata."""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from context_guard.storage import ensure_data_home, get_data_home

ROLES = ("academic", "technical", "business", "vi_en", "red_team")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prepare(data_home: Path, run_name: str = "m12_blind_v1") -> dict[str, Any]:
    normalized = data_home / "normalized"
    run_dir = data_home / "reviewer_runs" / run_name
    packet_dir = run_dir / "packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    dev = _read_jsonl(normalized / "natural_adversarial_v1_dev.jsonl")
    hidden = _read_jsonl(normalized / "natural_adversarial_v1_hidden.jsonl")
    labels_path = data_home / "benchmark_cache" / "natural_adversarial_v1_hidden_labels.jsonl"
    labels = {row["sample_id"]: row["label"] for row in _read_jsonl(labels_path)}
    records = dev + hidden
    mapping: dict[str, dict[str, str]] = {}
    blind_records: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        item_id = f"blind-{index:04d}"
        mapping[item_id] = {
            "sample_id": record["sample_id"],
            "gold_label": record["label"] if "label" in record else labels[record["sample_id"]],
            "split": record.get("split", "hidden"),
        }
        blind_records.append(
            {
                "item_id": item_id,
                "domain": record["domain"],
                "language": record["language"],
                "original_context": record["original_context"],
                "candidate_context": record["candidate_context"],
            }
        )
    (run_dir / "item_map.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for role_index, role in enumerate(ROLES):
        packet = list(blind_records)
        random.Random(20260729 + role_index).shuffle(packet)
        path = packet_dir / f"{role}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in packet:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "run": run_name,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "roles": list(ROLES),
        "records_per_role": len(blind_records),
        "blind_fields": ["item_id", "domain", "language", "original_context", "candidate_context"],
        "forbidden_fields": [
            "label",
            "gold_label",
            "mutation_type",
            "source_name",
            "source_record_id",
            "notes",
            "builder_rationale",
        ],
        "reviewer_contract": (
            "Return only one JSON object per item with item_id, verdict "
            "SAFE|UNSAFE|UNCERTAIN, confidence 0..1, rationale_code and "
            "reviewer_role. Do not infer hidden labels from filenames or order."
        ),
    }
    (run_dir / "review_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-home", type=Path, default=None)
    parser.add_argument("--run", default="m12_blind_v1")
    args = parser.parse_args()
    manifest = prepare(ensure_data_home(args.data_home or get_data_home()), args.run)
    print(json.dumps({"valid": True, **manifest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
