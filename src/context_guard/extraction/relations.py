from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Relation:
    subject: str
    relation: str
    object: str
    evidence: str
    confidence: float = 0.9


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "responsible_for",
        re.compile(
            r"(?P<subject>[A-ZÀ-Ỹ][\wÀ-ỹ-]*)\s+"
            r"(?:phụ trách|chịu trách nhiệm cho)\s+(?P<object>[^,.;]+)",
            re.I,
        ),
    ),
    (
        "responsible_for",
        re.compile(
            r"(?P<subject>[A-Z][\w-]*)\s+(?:is responsible for|owns)\s+(?P<object>[^,.;]+)", re.I
        ),
    ),
    (
        "has_role",
        re.compile(
            r"(?:(?:model|mô hình)\s+)?(?P<subject>[A-ZÀ-Ỹ][\wÀ-ỹ.-]*)\s+"
            r"(?:is used as|được dùng làm)\s+"
            r"(?P<object>target|draft|compressor|classifier)",
            re.I,
        ),
    ),
    (
        "has_threshold",
        re.compile(
            r"(?P<subject>accuracy|precision|recall|f1(?:[- ]score)?|auc|loss|score|metric|"
            r"độ chính xác|điểm)\s+"
            r"(?:must\s+be|should\s+be|at\s+least|at\s+most|no\s+less\s+than|"
            r"no\s+more\s+than|greater\s+than|less\s+than|>=|<=|>|<|=|"
            r"phải|tối thiểu|tối đa|ít nhất|không thấp hơn|không quá|lớn hơn|nhỏ hơn|"
            r"thấp hơn|cao hơn)\s*"
            r"(?P<object>(?:at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|"
            r">=|<=|>|<|=)?\s*\d+(?:[.,]\d+)?\s*(?:%|percent|phần\s*trăm)?)",
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    (
        "has_value",
        re.compile(
            r"(?P<subject>accuracy|precision|recall|f1(?:[- ]score)?|auc|loss|score|metric|"
            r"độ chính xác|điểm)\s+(?:is|was|achieved|đạt|là)\s*"
            r"(?P<object>\d+(?:[.,]\d+)?\s*(?:%|percent|phần\s*trăm)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "evaluated_on",
        re.compile(
            r"(?P<subject>accuracy|precision|recall|f1(?:[- ]score)?|auc|loss|score|metric|"
            r"độ chính xác|điểm)\s+(?:is|was|achieved|đạt|là)\s+"
            r"\d+(?:[.,]\d+)?\s*(?:%|percent|phần\s*trăm)\s+on\s+"
            r"(?P<object>[A-Za-zÀ-ỹ][\wÀ-ỹ.-]*)",
            re.IGNORECASE,
        ),
    ),
    (
        "belongs_to",
        re.compile(
            r"(?P<subject>[\w.-]+\.(?:py|json|yaml|yml|toml|ini|cfg|conf))\s+"
            r"(?:belongs\s+to|is\s+part\s+of|thuộc|nằm\s+trong)\s+"
            r"(?P<object>[\w.-]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "evaluated_on",
        re.compile(
            r"(?P<subject>[A-Za-zÀ-ỹ][\wÀ-ỹ.-]*|method|mô\s+hình)\s+"
            r"(?:was\s+)?(?:evaluated|tested)\s+on\s+(?P<object>[A-Za-zÀ-ỹ][\wÀ-ỹ.-]*)"
            r"|(?P<subject_vi>[A-Za-zÀ-ỹ][\wÀ-ỹ.-]*|method|mô\s+hình)\s+"
            r"được\s+đánh\s+giá\s+trên\s+(?P<object_vi>[A-Za-zÀ-ỹ][\wÀ-ỹ.-]*)",
            re.IGNORECASE,
        ),
    ),
    (
        "has_deadline",
        re.compile(
            r"(?P<subject>[\wÀ-ỹ -]+?)\s+"
            r"(?:deadline|hạn chót|hạn)\s+"
            r"(?P<object>\d{1,2}[/.]\d{1,2}[/.]\d{4}|\d{4}-\d{1,2}-\d{1,2})",
            re.I,
        ),
    ),
)


def extract_relations(text: str, language: str = "auto") -> list[Relation]:
    del language
    relations: list[Relation] = []
    for relation_name, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            subject = match.groupdict().get("subject") or match.groupdict().get("subject_vi")
            object_value = match.groupdict().get("object") or match.groupdict().get("object_vi")
            if subject is None or object_value is None:
                continue
            relations.append(
                Relation(
                    subject=" ".join(subject.split()).strip(" .,;:()[]{}"),
                    relation=relation_name,
                    object=" ".join(object_value.split()).strip(" .,;:()[]{}"),
                    evidence=match.group(0),
                )
            )
    return relations
