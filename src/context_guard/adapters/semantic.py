from __future__ import annotations

from context_guard.adapters.base import SemanticVerification


class UnavailableSemanticVerifier:
    """Explicit safe fallback; ML dependencies are intentionally optional."""

    name = "semantic-unavailable"

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification:
        del original_text, candidate_text
        return SemanticVerification(
            available=False, result=None, warning="semantic verifier unavailable"
        )
