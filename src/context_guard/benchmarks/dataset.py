from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TypedDict

from context_guard.adapters.mutations import generate_mutations


class DatasetRecord(TypedDict):
    id: str
    language: str
    domain: str
    original: str
    candidate: str
    label: str
    violation_types: list[str]
    critical_facts: list[str]
    label_status: str
    notes: str


def _safe_templates(language: str) -> list[tuple[str, str, str, str, list[str]]]:
    if language == "vi":
        return [
            (
                "general",
                "Ghi chú số {n} được lưu trong hồ sơ.",
                "Ghi chú số {n} được lưu trong hồ sơ.",
                "identity",
                ["{n}"],
            ),
            (
                "general",
                "Ngày kiểm tra là 30/08/2026.",
                "Ngày kiểm tra là 2026-08-30.",
                "date_format",
                ["2026-08-30"],
            ),
            (
                "academic",
                "Dataset XNLI đạt accuracy {p}%.",
                "Dataset XNLI đạt accuracy {p} phần trăm.",
                "percentage_format",
                ["{p}%"],
            ),
            (
                "academic",
                "Phương pháp dùng 4 bước trong benchmark.",
                "Phương pháp dùng bốn bước trong benchmark.",
                "word_rewrite",
                ["4"],
            ),
            (
                "business",
                "Chi phí là {money} VND.",
                "Chi phí là {money} VND.",
                "identity",
                ["{money} VND"],
            ),
            (
                "business",
                "Lan phụ trách báo cáo cuối tuần.",
                "Lan phụ trách báo cáo cuối tuần.",
                "identity",
                ["Lan"],
            ),
            (
                "technical",
                "Dùng Python 3.11 với file config.yaml.",
                "Dùng Python 3.11 với file `config.yaml`.",
                "quote_normalization",
                ["Python 3.11", "config.yaml"],
            ),
            (
                "technical",
                "Chạy lệnh `uv run pytest` trên Windows.",
                "Chạy lệnh uv run pytest trên Windows.",
                "code_quote",
                ["uv run pytest"],
            ),
        ]
    return [
        (
            "general",
            "Record number {n} is stored in the report.",
            "Record number {n} is stored in the report.",
            "identity",
            ["{n}"],
        ),
        (
            "general",
            "The review date is 30/08/2026.",
            "The review date is 2026-08-30.",
            "date_format",
            ["2026-08-30"],
        ),
        (
            "academic",
            "Dataset XNLI reached {p}% accuracy.",
            "Dataset XNLI reached {p} percent accuracy.",
            "percentage_format",
            ["{p}%"],
        ),
        (
            "academic",
            "The method used 4 steps in the benchmark.",
            "The method used four steps in the benchmark.",
            "word_rewrite",
            ["4"],
        ),
        (
            "business",
            "The cost is {money} USD.",
            "The cost is {money} USD.",
            "identity",
            ["{money} USD"],
        ),
        (
            "business",
            "Alice is responsible for the weekly report.",
            "Alice is responsible for the weekly report.",
            "identity",
            ["Alice"],
        ),
        (
            "technical",
            "Use Python 3.11 with config.yaml.",
            "Use Python 3.11 with `config.yaml`.",
            "quote_normalization",
            ["Python 3.11", "config.yaml"],
        ),
        (
            "technical",
            "Run `uv run pytest` on Windows.",
            "Run uv run pytest on Windows.",
            "code_quote",
            ["uv run pytest"],
        ),
    ]


def _unsafe_templates(language: str) -> list[tuple[str, str, str, str, list[str]]]:
    if language == "vi":
        return [
            (
                "general",
                "Không ghi đè hồ sơ số {n}.",
                "Ghi đè hồ sơ số {n}.",
                "negation_removed",
                ["Không"],
            ),
            ("general", "Hồ sơ có {n} mục.", "Hồ sơ có {changed} mục.", "number_changed", ["{n}"]),
            (
                "academic",
                "Kết quả đạt {p}% accuracy.",
                "Kết quả đạt {changed}% accuracy.",
                "percentage_changed",
                ["{p}%"],
            ),
            (
                "academic",
                "Model dùng 4 GB VRAM.",
                "Model dùng 4 MB VRAM.",
                "unit_changed",
                ["4 GB"],
            ),
            (
                "business",
                "Deadline là 30/08/2026.",
                "Deadline là 30/09/2026.",
                "date_changed",
                ["30/08/2026"],
            ),
            (
                "business",
                "Ngân sách là 20 triệu đồng.",
                "Ngân sách là 30 triệu đồng.",
                "money_changed",
                ["20 triệu đồng"],
            ),
            (
                "business",
                "Chỉ thanh toán nếu hợp đồng được ký.",
                "Thanh toán.",
                "condition_removed",
                ["nếu"],
            ),
            (
                "business",
                "Triển khai trừ khi kiểm thử thất bại.",
                "Triển khai.",
                "exception_removed",
                ["trừ khi"],
            ),
            (
                "technical",
                "Phải dùng Python 3.11.",
                "Nên dùng Python 3.11.",
                "modality_changed",
                ["Phải"],
            ),
            (
                "technical",
                "ModelB được dùng làm target.",
                "ModelB được dùng làm draft.",
                "model_role_changed",
                ["target"],
            ),
        ]
    return [
        (
            "general",
            "Do not overwrite record {n}.",
            "Overwrite record {n}.",
            "negation_removed",
            ["Do not"],
        ),
        (
            "general",
            "The report has {n} items.",
            "The report has {changed} items.",
            "number_changed",
            ["{n}"],
        ),
        (
            "academic",
            "The result achieved {p}% accuracy.",
            "The result achieved {changed}% accuracy.",
            "percentage_changed",
            ["{p}%"],
        ),
        (
            "academic",
            "The model uses 4 GB of VRAM.",
            "The model uses 4 MB of VRAM.",
            "unit_changed",
            ["4 GB"],
        ),
        (
            "business",
            "The deadline is 30/08/2026.",
            "The deadline is 30/09/2026.",
            "date_changed",
            ["30/08/2026"],
        ),
        (
            "business",
            "The budget is 20 million dollars.",
            "The budget is 30 million dollars.",
            "money_changed",
            ["20 million dollars"],
        ),
        ("business", "Pay if the contract is signed.", "Pay.", "condition_removed", ["if"]),
        ("business", "Deploy unless testing fails.", "Deploy.", "exception_removed", ["unless"]),
        (
            "technical",
            "You must use Python 3.11.",
            "You should use Python 3.11.",
            "modality_changed",
            ["must"],
        ),
        (
            "technical",
            "ModelB is used as target.",
            "ModelB is used as draft.",
            "model_role_changed",
            ["target"],
        ),
    ]


def build_provisional_golden() -> list[DatasetRecord]:
    records: list[DatasetRecord] = []
    for language in ("vi", "en"):
        safe = _safe_templates(language)
        unsafe = _unsafe_templates(language)
        for label, templates in (("SAFE", safe), ("UNSAFE", unsafe)):
            for index in range(75):
                domain = ("general", "academic", "business", "technical")[len(records) % 4]
                domain_templates = [template for template in templates if template[0] == domain]
                template = domain_templates[(index // 4) % len(domain_templates)]
                _, original, candidate, mutation, facts = template
                variant = index // len(domain_templates)
                values = {
                    "n": str(100 + variant * 7 + index % len(templates)),
                    "changed": str(101 + variant * 7 + index % len(templates)),
                    "p": str(80 + variant % 15),
                    "money": str(20 + variant),
                }
                rendered_original = original.format(**values)
                rendered_candidate = candidate.format(**values)
                rendered_facts = [fact.format(**values) for fact in facts]
                sample_suffix = f" [sample-{language}-{label.lower()}-{index:03d}]"
                records.append(
                    {
                        "id": f"{language.lower()}-{label.lower()}-{index:03d}",
                        "language": language,
                        "domain": domain,
                        "original": rendered_original + sample_suffix,
                        "candidate": rendered_candidate + sample_suffix,
                        "label": label,
                        "violation_types": [] if label == "SAFE" else [mutation],
                        "critical_facts": rendered_facts,
                        "label_status": "synthetic_unverified",
                        "notes": (
                            "Provisional generated sample; manual audit required "
                            "before quality claims."
                        ),
                    }
                )
    return records


def write_jsonl(records: list[DatasetRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[DatasetRecord]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def validate_dataset(records: list[DatasetRecord], expected_count: int = 300) -> dict[str, object]:
    required = {
        "id",
        "language",
        "domain",
        "original",
        "candidate",
        "label",
        "violation_types",
        "critical_facts",
        "label_status",
        "notes",
    }
    if len(records) != expected_count:
        raise ValueError(f"dataset sample count {len(records)} != expected {expected_count}")
    if any(set(record) != required for record in records):
        raise ValueError("dataset schema fields do not match the locked contract")
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("dataset contains duplicate ids")
    counts = Counter((record["language"], record["label"]) for record in records)
    expected = {("vi", "SAFE"): 75, ("vi", "UNSAFE"): 75, ("en", "SAFE"): 75, ("en", "UNSAFE"): 75}
    if counts != expected:
        raise ValueError(f"dataset language/label balance mismatch: {counts}")
    if any(record["label"] not in {"SAFE", "UNSAFE"} for record in records):
        raise ValueError("dataset has an unsupported label")
    return {
        "sample_count": len(records),
        "counts": {
            f"{language}/{label}": count
            for (language, label), count in sorted(counts.items())
        },
        "label_statuses": sorted({record["label_status"] for record in records}),
    }


def build_provisional_mutations(seed: int = 20260729, minimum: int = 2000) -> list[DatasetRecord]:
    records: list[DatasetRecord] = []
    seen: set[tuple[str, str, str]] = set()
    variant = 0
    while len(records) < minimum and variant < 400:
        language = "en" if variant % 2 else "vi"
        minor = 11 + variant % 10
        percent = 70 + variant % 30
        money = 10 + variant
        day = 13 + variant % 16
        if language == "vi":
            original = (
                f"Không triển khai Python 3.{minor} nếu accuracy ít nhất {percent}% "
                f"trừ khi Lan phê duyệt. Dùng 4 GB RAM, ngân sách {money} triệu đồng, "
                f"deadline {day:02d}/08/2026, file config_{variant}.yaml; "
                "chạy python app.py --safe=true. ModelB được dùng làm target."
            )
        else:
            original = (
                f"Do not deploy Python 3.{minor} if accuracy is at least {percent}% "
                f"unless Alice approves. Use 4 GB RAM, budget {money} USD, "
                f"deadline {day:02d}/08/2026, file config_{variant}.yaml; "
                "run python app.py --safe=true. ModelB is used as target."
            )
        for mutation in generate_mutations(original, seed=seed + variant):
            key = (original, mutation.candidate, mutation.mutation_type)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "id": f"mutation-{len(records):05d}",
                    "language": language,
                    "domain": "technical" if variant % 3 else "business",
                    "original": original,
                    "candidate": mutation.candidate,
                    "label": "UNSAFE",
                    "violation_types": [mutation.mutation_type],
                    "critical_facts": [mutation.source_span],
                    "label_status": "synthetic_unverified",
                    "notes": (
                        "Controlled deterministic mutation; manual audit required "
                        "before quality claims."
                    ),
                }
            )
        safe_candidate = original.replace("  ", " ")
        safe_key = (original, safe_candidate, "safe_identity")
        if safe_key not in seen:
            seen.add(safe_key)
            records.append(
                {
                    "id": f"mutation-{len(records):05d}",
                    "language": language,
                    "domain": "technical" if variant % 3 else "business",
                    "original": original,
                    "candidate": safe_candidate,
                    "label": "SAFE",
                    "violation_types": [],
                    "critical_facts": [],
                    "label_status": "synthetic_unverified",
                    "notes": (
                        "Controlled safe identity transformation; manual audit required "
                        "before quality claims."
                    ),
                }
            )
        date_source = f"deadline {day:02d}/08/2026"
        date_target = f"deadline 2026-08-{day:02d}"
        safe_date_candidate = original.replace(date_source, date_target, 1)
        safe_date_key = (original, safe_date_candidate, "safe_date_format")
        if safe_date_candidate != original and safe_date_key not in seen:
            seen.add(safe_date_key)
            records.append(
                {
                    "id": f"mutation-{len(records):05d}",
                    "language": language,
                    "domain": "technical" if variant % 3 else "business",
                    "original": original,
                    "candidate": safe_date_candidate,
                    "label": "SAFE",
                    "violation_types": ["safe_date_format"],
                    "critical_facts": [date_source],
                    "label_status": "synthetic_unverified",
                    "notes": (
                        "Controlled safe date-format transformation; manual audit required "
                        "before quality claims."
                    ),
                }
            )
        variant += 1
    if len(records) < minimum:
        raise ValueError(f"could only generate {len(records)} unique mutation records")
    return records


def validate_mutation_dataset(
    records: list[DatasetRecord], minimum_count: int = 2000
) -> dict[str, object]:
    required = {
        "id",
        "language",
        "domain",
        "original",
        "candidate",
        "label",
        "violation_types",
        "critical_facts",
        "label_status",
        "notes",
    }
    if len(records) < minimum_count:
        raise ValueError(f"mutation dataset sample count {len(records)} < minimum {minimum_count}")
    if any(set(record) != required for record in records):
        raise ValueError("mutation dataset schema fields do not match the locked contract")
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("mutation dataset contains duplicate ids")
    unique_candidates = {
        (record["original"], record["candidate"], tuple(record["violation_types"]))
        for record in records
    }
    if len(unique_candidates) != len(records):
        raise ValueError("mutation dataset contains duplicate candidates")
    if {record["label"] for record in records} != {"SAFE", "UNSAFE"}:
        raise ValueError("mutation dataset must contain SAFE and UNSAFE records")
    return {
        "sample_count": len(records),
        "labels": dict(Counter(record["label"] for record in records)),
        "unique_candidates": len(unique_candidates),
    }
