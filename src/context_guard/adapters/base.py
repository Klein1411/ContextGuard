from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from context_guard.schemas.models import ProtectedSpan, ValidationResult


class CompressorAdapter(Protocol):
    name: str

    def compress(self, text: str, protected_spans: list[ProtectedSpan] | None = None) -> str: ...


@dataclass(frozen=True)
class SemanticVerification:
    available: bool
    result: ValidationResult | None
    warning: str | None = None


class SemanticVerifierAdapter(Protocol):
    name: str

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification: ...
