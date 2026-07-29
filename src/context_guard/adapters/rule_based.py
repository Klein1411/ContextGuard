from __future__ import annotations

import re

from context_guard.schemas.models import ProtectedSpan


class RuleBasedCompressor:
    """Deterministic baseline compressor used only for benchmark candidates."""

    name = "rule-based"
    _FILLERS = re.compile(r"\b(?:um+|uh+|like|you know|à|ờ|kiểu như|thì là)\b", re.I)

    def compress(self, text: str, protected_spans: list[ProtectedSpan] | None = None) -> str:
        del protected_spans
        compact = self._FILLERS.sub("", text)
        compact = re.sub(r"\s+", " ", compact).strip()
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]
        if len(sentences) <= 2:
            return compact
        return " ".join(sentences[::2])
