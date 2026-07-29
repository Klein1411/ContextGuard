from __future__ import annotations

import re

_ENTITY = re.compile(r"\b(?:[A-ZÀ-Ỹ][\wÀ-ỹ-]*|[A-ZÀ-Ỹ][\wÀ-ỹ-]*(?:\s+[A-ZÀ-Ỹ][\wÀ-ỹ-]*)+)\b")
_IGNORE = {"The", "This", "That", "These", "Those", "Model", "Use", "Do", "Deploy", "Không"}


def extract_entities(text: str) -> list[str]:
    values: list[str] = []
    for match in _ENTITY.finditer(text):
        value = match.group(0).strip(" .,;:()[]{}")
        if (
            value in _IGNORE
            or len(value) < 2
            or value.isdigit()
            or not value[0].isupper()
        ):
            continue
        if value not in values:
            values.append(value)
    return values
