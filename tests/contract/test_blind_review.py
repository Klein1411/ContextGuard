from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.aggregate_review as aggregate_module
from scripts.aggregate_review import aggregate
from scripts.prepare_review import prepare


def test_prepare_review_strips_builder_fields(tmp_path: Path) -> None:
    data_home = tmp_path / "data"
    normalized = data_home / "normalized"
    cache = data_home / "benchmark_cache"
    normalized.mkdir(parents=True)
    cache.mkdir(parents=True)
    dev_row = {
        "sample_id": "sample-dev",
        "domain": "general",
        "language": "en",
        "original_context": "original",
        "candidate_context": "candidate",
        "label": "SAFE",
        "mutation_type": "none",
        "source_name": "secret",
        "notes": "secret",
        "split": "dev",
    }
    hidden_row = {key: value for key, value in dev_row.items() if key not in {"label", "split"}}
    hidden_row["sample_id"] = "sample-hidden"
    (normalized / "natural_adversarial_v1_dev.jsonl").write_text(
        json.dumps(dev_row) + "\n", encoding="utf-8"
    )
    (normalized / "natural_adversarial_v1_hidden.jsonl").write_text(
        json.dumps(hidden_row) + "\n", encoding="utf-8"
    )
    (cache / "natural_adversarial_v1_hidden_labels.jsonl").write_text(
        json.dumps({"sample_id": "sample-hidden", "label": "UNSAFE"}) + "\n",
        encoding="utf-8",
    )
    manifest = prepare(data_home, "run")
    packet = json.loads(
        (data_home / "reviewer_runs" / "run" / "packets" / "academic.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert manifest["records_per_role"] == 2
    assert set(packet) == {
        "item_id",
        "domain",
        "language",
        "original_context",
        "candidate_context",
    }


def test_aggregate_computes_pairwise_and_excludes_ties(tmp_path: Path) -> None:
    data_home = tmp_path / "data"
    run_dir = data_home / "reviewer_runs" / "run"
    reviews = run_dir / "reviews"
    reviews.mkdir(parents=True)
    mapping = {
        "item-1": {"sample_id": "s1", "gold_label": "SAFE", "split": "dev"},
        "item-2": {"sample_id": "s2", "gold_label": "UNSAFE", "split": "hidden"},
    }
    (run_dir / "item_map.json").write_text(json.dumps(mapping), encoding="utf-8")
    for role_index, role in enumerate(aggregate_module.ROLES):
        verdicts = ["SAFE", "UNSAFE" if role_index < 4 else "SAFE"]
        rows = [
            {
                "item_id": item_id,
                "verdict": verdict,
                "confidence": 0.8,
                "rationale_code": "preserved",
                "reviewer_role": role,
            }
            for item_id, verdict in zip(mapping, verdicts, strict=True)
        ]
        (reviews / f"{role}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
    summary = aggregate(data_home, "run")
    assert summary["records"] == 2
    assert summary["adjudication"]["unresolved_excluded"] == 0
    assert summary["raw_agreement"]["pairwise_rate"]["academic__technical"] == 1.0
