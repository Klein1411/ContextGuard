from __future__ import annotations

import re

from context_guard.schemas.models import ProtectedSpan


class RuleBasedCompressor:
    """Deterministic baseline compressor that keeps sentences with protected facts."""

    name = "rule-based"
    _FILLERS = re.compile(r"\b(?:um+|uh+|like|you know|à|ờ|kiểu như|thì là)\b", re.I)

    def compress(self, text: str, protected_spans: list[ProtectedSpan] | None = None) -> str:
        protected = protected_spans or []
        markers: dict[str, str] = {}
        compact = text
        for index, span in enumerate(
            sorted(protected, key=lambda item: (len(item.text), item.start), reverse=True)
        ):
            marker = f"__CONTEXTGUARD_PROTECTED_{index}__"
            if span.text and span.text in compact:
                compact = compact.replace(span.text, marker, 1)
                markers[marker] = span.text
        compact = self._FILLERS.sub("", compact)
        compact = re.sub(r"\s+", " ", compact).strip()
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]
        if len(sentences) <= 2:
            result = compact
        else:
            result = " ".join(
                sentence
                for index, sentence in enumerate(sentences)
                if index % 2 == 0 or any(marker in sentence for marker in markers)
            )
        for marker, original in markers.items():
            result = result.replace(marker, original)
        return result
