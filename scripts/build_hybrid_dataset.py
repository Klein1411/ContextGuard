from __future__ import annotations

import argparse
from pathlib import Path

from context_guard.benchmarks.dataset import write_jsonl

DATES = ["03/04/2026", "04/05/2026", "05/06/2026", "06/07/2026", "07/08/2026"]

TEMPLATES = [
    (
        "en",
        "academic",
        "The blue plan is approved on {date}.",
        "The blue plan receives approval on {date}.",
        "entailment",
        "SAFE",
    ),
    (
        "en",
        "business",
        "The project is ready on {date}.",
        "On {date}, the project is ready.",
        "entailment",
        "SAFE",
    ),
    (
        "en",
        "technical",
        "The system uses a {date} token.",
        "A {date} token is used by the system.",
        "entailment",
        "SAFE",
    ),
    ("en", "general", "{date} is recorded.", "The date {date} is recorded.", "entailment", "SAFE"),
    (
        "en",
        "business",
        "The meeting is scheduled on {date}.",
        "The meeting is scheduled for {date}.",
        "entailment",
        "SAFE",
    ),
    (
        "en",
        "academic",
        "The blue plan is approved on {date}.",
        "The blue plan is rejected on {date}.",
        "contradiction",
        "UNSAFE",
    ),
    (
        "en",
        "business",
        "The project is ready on {date}.",
        "The project is delayed on {date}.",
        "contradiction",
        "UNSAFE",
    ),
    (
        "en",
        "technical",
        "The system uses a {date} token.",
        "The system discards a {date} token.",
        "contradiction",
        "UNSAFE",
    ),
    ("en", "general", "{date} is recorded.", "{date} is missing.", "contradiction", "UNSAFE"),
    (
        "en",
        "business",
        "The meeting is scheduled on {date}.",
        "The meeting is cancelled on {date}.",
        "contradiction",
        "UNSAFE",
    ),
    (
        "vi",
        "academic",
        "Kế hoạch xanh được phê duyệt vào {date}.",
        "Kế hoạch xanh nhận phê duyệt vào {date}.",
        "entailment",
        "SAFE",
    ),
    (
        "vi",
        "business",
        "Dự án sẵn sàng vào {date}.",
        "Dự án đã sẵn sàng vào {date}.",
        "entailment",
        "SAFE",
    ),
    (
        "vi",
        "technical",
        "Hệ thống dùng token {date}.",
        "Hệ thống sử dụng token {date}.",
        "entailment",
        "SAFE",
    ),
    ("vi", "general", "{date} được ghi nhận.", "Ngày {date} được ghi nhận.", "entailment", "SAFE"),
    (
        "vi",
        "business",
        "Cuộc họp được lên lịch vào {date}.",
        "Cuộc họp được lên lịch cho {date}.",
        "entailment",
        "SAFE",
    ),
    (
        "vi",
        "academic",
        "Kế hoạch xanh được phê duyệt vào {date}.",
        "Kế hoạch xanh bị từ chối vào {date}.",
        "contradiction",
        "UNSAFE",
    ),
    (
        "vi",
        "business",
        "Dự án sẵn sàng vào {date}.",
        "Dự án bị trì hoãn vào {date}.",
        "contradiction",
        "UNSAFE",
    ),
    (
        "vi",
        "technical",
        "Hệ thống dùng token {date}.",
        "Hệ thống loại bỏ token {date}.",
        "contradiction",
        "UNSAFE",
    ),
    ("vi", "general", "{date} được ghi nhận.", "{date} bị thiếu.", "contradiction", "UNSAFE"),
    (
        "vi",
        "business",
        "Cuộc họp được lên lịch vào {date}.",
        "Cuộc họp bị hủy vào {date}.",
        "contradiction",
        "UNSAFE",
    ),
]


def build() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for template_index, (language, domain, original, candidate, kind, label) in enumerate(
        TEMPLATES
    ):
        for variant, date in enumerate(DATES):
            records.append(
                {
                    "id": f"hybrid-{template_index:02d}-{variant:02d}",
                    "language": language,
                    "domain": domain,
                    "original": original.format(date=date),
                    "candidate": candidate.format(date=date),
                    "label": label,
                    "violation_types": [] if label == "SAFE" else [kind],
                    "critical_facts": [date],
                    "label_status": "audited",
                    "notes": (
                        "Audited controlled entailment/contradiction pair; ambiguous date forces "
                        "the optional semantic path."
                    ),
                }
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the controlled hybrid semantic dataset.")
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/datasets/hybrid_v0_audited.jsonl")
    )
    args = parser.parse_args()
    records = build()
    write_jsonl(records, args.output)
    print(f"wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
