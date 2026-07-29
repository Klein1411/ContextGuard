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
            r"(?:model|mô hình)\s+(?P<subject>[\w.-]+)\s+"
            r"(?:is used as|được dùng làm)\s+"
            r"(?P<object>target|draft|compressor|classifier)",
            re.I,
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
            relations.append(
                Relation(
                    subject=" ".join(match.group("subject").split()).strip(),
                    relation=relation_name,
                    object=" ".join(match.group("object").split()).strip(),
                    evidence=match.group(0),
                )
            )
    return relations
