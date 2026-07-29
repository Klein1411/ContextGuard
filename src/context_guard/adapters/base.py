from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from context_guard.schemas.models import ProtectedSpan, ValidationResult


class CompressorAdapter(Protocol):
    name: str

    def compress(self, text: str, protected_spans: list[ProtectedSpan] | None = None) -> str: ...


class AdapterUnavailableError(RuntimeError):
    """Raised when an optional candidate generator is not installed or configured."""


class UnavailableCompressor:
    """Explicit safe placeholder for optional compressor backends."""

    available = False

    def __init__(self, name: str) -> None:
        self.name = name

    def compress(self, text: str, protected_spans: list[ProtectedSpan] | None = None) -> str:
        del text, protected_spans
        raise AdapterUnavailableError(
            f"compressor adapter '{self.name}' is unavailable; "
            "install/configure its optional backend"
        )


@dataclass(frozen=True)
class SemanticVerification:
    available: bool
    result: ValidationResult | None
    warning: str | None = None


class SemanticVerifierAdapter(Protocol):
    name: str

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification: ...
