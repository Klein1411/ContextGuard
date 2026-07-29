from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Mutation:
    mutation_type: str
    seed: int
    source_span: str
    replacement: str
    candidate: str
    expected_label: str


def _replace_first(
    text: str, pattern: str, replacement: str, flags: int = re.I
) -> tuple[str, str, str] | None:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    source = match.group(0)
    return text[: match.start()] + replacement + text[match.end() :], source, replacement


def _mutation_specs() -> dict[str, Callable[[str], tuple[str, str, str] | None]]:
    return {
        "negation_removed": lambda text: _replace_first(
            text, r"\b(?:không được|không|chưa|never|must not|do not|not)\b\s*", ""
        ),
        "number_changed": lambda text: _replace_first(
            text, r"(?<![\w.])\d+(?:[.,]\d+)*(?![\w.])", "999"
        ),
        "percentage_changed": lambda text: _replace_first(
            text, r"\d+(?:[.,]\d+)?\s*(?:%|percent|phần trăm)", "80%"
        ),
        "unit_changed": lambda text: _replace_first(
            text, r"\b(?:GB|MB|TB|KB|ms|s|kg|g|km|m)\b", "MB"
        ),
        "date_changed": lambda text: _replace_first(
            text, r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4})\b", "01/01/2030"
        ),
        "money_changed": lambda text: _replace_first(
            text, r"(?:[$€£]\s?\d[\d,.]*|\d[\d,.]*\s?(?:USD|VND|đồng|triệu đồng))", "999 USD"
        ),
        "comparison_reversed": lambda text: _replace_first(
            text, r">=|<=|>|<|at least|at most|ít nhất|không quá", "<"
        ),
        "condition_removed": lambda text: _replace_first(
            text, r"\b(?:if|nếu|only if|chỉ khi|provided that|miễn là)\b[^,.;]*", ""
        ),
        "exception_removed": lambda text: _replace_first(
            text, r"\b(?:unless|except|trừ khi|ngoại trừ)\b[^,.;]*", ""
        ),
        "entity_changed": lambda text: _replace_first(text, r"\bAlice\b|\bBob\b|\bPython\b", "Eve"),
        "responsible_changed": lambda text: _replace_first(text, r"\bAlice\b|\bBob\b", "Bob"),
        "model_role_changed": lambda text: _replace_first(
            text, r"\b(?:target|draft|compressor|classifier)\b", "target"
        ),
        "version_changed": lambda text: _replace_first(
            text, r"\b(?:Python|Node|CUDA|FastAPI|PyTorch)\s+\d+\.\d+(?:\.\d+)?\b", "Python 3.12"
        ),
        "filename_changed": lambda text: _replace_first(
            text, r"\b[\w-]+\.(?:py|json|yaml|yml|txt|csv)\b", "other.py"
        ),
        "config_changed": lambda text: _replace_first(
            text, r"\b(?:true|false|enabled|disabled)\b", "false"
        ),
        "command_changed": lambda text: _replace_first(
            text, r"\b(?:python|uv|pip|docker)\s+[^.;\n]+", "python wrong.py"
        ),
        "boolean_changed": lambda text: _replace_first(
            text, r"\b(?:true|false|True|False)\b", "false"
        ),
    }


def generate_mutations(text: str, seed: int = 20260729) -> list[Mutation]:
    rng = random.Random(seed)
    mutations: list[Mutation] = []
    for mutation_type, function in _mutation_specs().items():
        result = function(text)
        if result is None:
            continue
        candidate, source, replacement = result
        mutations.append(
            Mutation(
                mutation_type=mutation_type,
                seed=rng.randrange(1_000_000_000),
                source_span=source,
                replacement=replacement,
                candidate=candidate,
                expected_label="UNSAFE",
            )
        )
    return mutations
