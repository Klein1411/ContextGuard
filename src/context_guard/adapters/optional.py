from __future__ import annotations

from context_guard.adapters.base import UnavailableCompressor


class TokenLevelCompressor(UnavailableCompressor):
    """Adapter boundary for an optional token-level compressor (for example LLMLingua)."""

    def __init__(self) -> None:
        super().__init__("token-level-unavailable")


class LLMSummarizerCompressor(UnavailableCompressor):
    """Adapter boundary for an optional local/API summarizer, disabled by default."""

    def __init__(self) -> None:
        super().__init__("llm-summarizer-unavailable")
