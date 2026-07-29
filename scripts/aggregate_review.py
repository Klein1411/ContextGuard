"""Validate and aggregate M12 blind multi-agent AI reviewer outputs."""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any

from context_guard.storage import ensure_data_home, get_data_home

ROLES = ("academic", "technical", "business", "vi_en", "red_team")
VERDICTS = ("SAFE", "UNSAFE", "UNCERTAIN")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _fleiss_kappa(matrix: list[list[str]]) -> float:
    if not matrix:
        return 0.0
    category_counts = [sum(row.count(category) for row in matrix) for category in VERDICTS]
    n = len(matrix[0])
    total = len(matrix) * n
    proportions = [count / total for count in category_counts]
    expected = sum(value * value for value in proportions)
    observed = sum(
        (sum(count * count for count in Counter(row).values()) - n) / (n * (n - 1))
        for row in matrix
    ) / len(matrix)
    return 0.0 if expected == 1 else (observed - expected) / (1 - expected)


def aggregate(data_home: Path, run_name: str = "m12_blind_v1") -> dict[str, Any]:
    run_dir = data_home / "reviewer_runs" / run_name
    review_dir = run_dir / "reviews"
    mapping = json.loads((run_dir / "item_map.json").read_text(encoding="utf-8"))
    by_role: dict[str, dict[str, dict[str, Any]]] = {}
    validation_errors: list[str] = []
    for role in ROLES:
        path = review_dir / f"{role}.jsonl"
        if not path.exists():
            validation_errors.append(f"missing:{role}")
            continue
        rows = _read_jsonl(path)
        by_role[role] = {}
        for row in rows:
            forbidden = {
                "label",
                "gold_label",
                "mutation_type",
                "source_name",
                "source_record_id",
                "notes",
            }
            if forbidden.intersection(row):
                validation_errors.append(f"forbidden_field:{role}:{row.get('item_id')}")
            if row.get("verdict") not in VERDICTS:
                validation_errors.append(f"invalid_verdict:{role}:{row.get('item_id')}")
            confidence = row.get("confidence")
            if not isinstance(confidence, (float, int)) or not 0 <= confidence <= 1:
                validation_errors.append(f"invalid_confidence:{role}:{row.get('item_id')}")
            item_id = row.get("item_id")
            if item_id in by_role[role]:
                validation_errors.append(f"duplicate_item:{role}:{item_id}")
            by_role[role][item_id] = row
        if len(rows) != len(mapping):
            validation_errors.append(f"count:{role}:{len(rows)}")
        if set(by_role[role]) != set(mapping):
            validation_errors.append(f"coverage:{role}")
    if validation_errors:
        raise RuntimeError("; ".join(validation_errors[:20]))

    rows = []
    matrix = []
    for item_id in mapping:
        verdicts = [by_role[role][item_id]["verdict"] for role in ROLES]
        counts = Counter(verdicts)
        top = counts.most_common()
        adjudicated = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "UNRESOLVED"
        rows.append(
            {
                "item_id": item_id,
                "verdicts": dict(zip(ROLES, verdicts, strict=True)),
                "adjudicated_verdict": adjudicated,
                "construction_label": mapping[item_id]["gold_label"],
                "split": mapping[item_id]["split"],
            }
        )
        matrix.append(verdicts)

    pairwise: dict[str, float] = {}
    for left, right in itertools.combinations(ROLES, 2):
        pairwise[f"{left}__{right}"] = sum(
            row[left] == row[right] for row in (item["verdicts"] for item in rows)
        ) / len(rows)
    unanimous = sum(len(set(row["verdicts"].values())) == 1 for row in rows) / len(rows)
    resolved = [row for row in rows if row["adjudicated_verdict"] != "UNRESOLVED"]
    construction_alignment = sum(
        row["adjudicated_verdict"] == row["construction_label"] for row in resolved
    ) / len(resolved) if resolved else 0.0
    summary = {
        "run": run_name,
        "review_type": "blind multi-agent AI review",
        "roles": list(ROLES),
        "records": len(rows),
        "raw_agreement": {
            "unanimous_rate": unanimous,
            "pairwise_rate_mean": sum(pairwise.values()) / len(pairwise),
            "pairwise_rate": pairwise,
            "fleiss_kappa": _fleiss_kappa(matrix),
        },
        "adjudication": {
            "resolved": len(resolved),
            "unresolved_excluded": len(rows) - len(resolved),
            "verdict_counts": dict(Counter(row["adjudicated_verdict"] for row in rows)),
            "construction_label_alignment": construction_alignment,
            "interpretation": (
                "Alignment is against controlled construction labels only; it is not "
                "human or domain-expert truth validation."
            ),
        },
        "limitations": [
            "Reviewers are AI agents, not human/domain experts.",
            "Raw reviewer outputs remain outside Git under reviewer_runs.",
            "UNCERTAIN/ties are excluded from adjudicated agreement and alignment.",
        ],
    }
    (run_dir / "review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    public_path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "final"
        / "m12_review_summary.json"
    )
    public_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "adjudicated.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-home", type=Path, default=None)
    parser.add_argument("--run", default="m12_blind_v1")
    args = parser.parse_args()
    summary = aggregate(ensure_data_home(args.data_home or get_data_home()), args.run)
    print(
        json.dumps(
            {
                "valid": True,
                "records": summary["records"],
                "fleiss_kappa": summary["raw_agreement"]["fleiss_kappa"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
