from __future__ import annotations

import importlib

from context_guard.adapters.base import AdapterUnavailableError, UnavailableCompressor
from context_guard.schemas.models import ProtectedSpan


class TokenLevelCompressor(UnavailableCompressor):
    """Adapter boundary for an optional token-level compressor (for example LLMLingua)."""

    def __init__(self) -> None:
        super().__init__("token-level-unavailable")


class LLMSummarizerCompressor(UnavailableCompressor):
    """Adapter boundary for an optional local/API summarizer, disabled by default."""

    def __init__(self) -> None:
        super().__init__("llm-summarizer-unavailable")


class LLMLingua2Compressor:
    """Opt-in LLMLingua-2 adapter with lazy, revision-pinned model loading."""

    name = "llmlingua-2"
    model_id = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
    model_revision = "ebaba9b"
    model_license = "MIT"

    def __init__(
        self,
        *,
        device: str = "auto",
        local_files_only: bool = False,
        rate: float = 0.5,
    ) -> None:
        if not 0.0 < rate <= 1.0:
            raise ValueError("rate must be in the interval (0, 1]")
        self.device = device
        self.local_files_only = local_files_only
        self.rate = rate
        self._compressor: object | None = None

    def _load(self) -> None:
        if self._compressor is not None:
            return
        try:
            torch = importlib.import_module("torch")
            llmlingua = importlib.import_module("llmlingua")
        except ModuleNotFoundError as exc:
            raise AdapterUnavailableError(
                "LLMLingua-2 requires the optional 'compressors' dependency group"
            ) from exc
        if self.device == "auto":
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            resolved_device = self.device
        model_config = {
            "revision": self.model_revision,
            "local_files_only": self.local_files_only,
        }
        try:
            self._compressor = llmlingua.PromptCompressor(
                model_name=self.model_id,
                device_map=resolved_device,
                model_config=model_config,
                use_llmlingua2=True,
            )
        except Exception as exc:
            raise AdapterUnavailableError(
                f"LLMLingua-2 model is unavailable: {type(exc).__name__}"
            ) from exc

    def compress(
        self, text: str, protected_spans: list[ProtectedSpan] | None = None
    ) -> str:
        self._load()
        if self._compressor is None:
            raise AdapterUnavailableError("LLMLingua-2 compressor did not initialize")
        force_tokens = [span.text for span in (protected_spans or []) if span.text]
        try:
            result = self._compressor.compress_prompt(  # type: ignore[attr-defined]
                [text],
                rate=self.rate,
                force_tokens=force_tokens,
                force_reserve_digit=True,
            )
            compressed = result.get("compressed_prompt")
        except Exception as exc:
            raise AdapterUnavailableError(
                f"LLMLingua-2 compression failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(compressed, str) or not compressed.strip():
            raise AdapterUnavailableError("LLMLingua-2 returned an empty candidate")
        return compressed
