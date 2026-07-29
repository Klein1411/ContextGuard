from __future__ import annotations

import importlib
from time import perf_counter
from typing import Any

from context_guard.adapters.base import AdapterUnavailableError, SemanticVerification
from context_guard.normalization.text import detect_language
from context_guard.schemas.models import (
    RecommendedAction,
    RiskLevel,
    SafetyStatus,
    ValidationResult,
    Violation,
)


class UnavailableSemanticVerifier:
    """Explicit safe fallback; ML dependencies are intentionally optional."""

    name = "semantic-unavailable"

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification:
        del original_text, candidate_text
        return SemanticVerification(
            available=False, result=None, warning="semantic verifier unavailable"
        )


class TransformersSemanticVerifier:
    """Opt-in multilingual NLI verifier with lazy, revision-pinned loading.

    The deterministic core never imports this adapter. Installing the optional
    ``semantic`` extra and constructing this class explicitly enables model
    loading; missing packages, download failures, and inference failures return
    an unavailable result so callers keep the safe deterministic fallback.
    """

    name = "transformers-nli"
    model_id = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    model_revision = "add259b"
    model_license = "MIT"

    def __init__(
        self,
        *,
        device: str = "auto",
        local_files_only: bool = False,
        entailment_threshold: float = 0.85,
    ) -> None:
        self.device = device
        self.local_files_only = local_files_only
        self.entailment_threshold = entailment_threshold
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._resolved_device: str | None = None

    def _load(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        try:
            torch: Any = importlib.import_module("torch")
            transformers_module: Any = importlib.import_module("transformers")
        except ModuleNotFoundError as exc:
            raise AdapterUnavailableError(
                "semantic verifier requires the optional 'semantic' dependency group"
            ) from exc
        AutoModelForSequenceClassification = transformers_module.AutoModelForSequenceClassification
        AutoTokenizer = transformers_module.AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.model_revision,
            local_files_only=self.local_files_only,
            use_fast=False,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_id,
            revision=self.model_revision,
            local_files_only=self.local_files_only,
        )
        if self.device == "auto":
            resolved = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            resolved = self.device
        model.to(resolved)
        model.eval()
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch
        self._resolved_device = resolved

    def verify(self, original_text: str, candidate_text: str) -> SemanticVerification:
        started = perf_counter()
        try:
            self._load()
            assert self._tokenizer is not None
            assert self._model is not None
            assert self._torch is not None
            encoded = self._tokenizer(
                original_text,
                candidate_text,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            encoded = {key: value.to(self._resolved_device) for key, value in encoded.items()}
            with self._torch.inference_mode():
                logits = self._model(**encoded).logits
            probabilities = self._torch.softmax(logits, dim=-1)[0].detach().cpu().tolist()
            labels = {
                int(index): str(label).casefold()
                for index, label in self._model.config.id2label.items()
            }
            scores = {labels[index]: float(score) for index, score in enumerate(probabilities)}
            entailment = scores.get("entailment", 0.0)
            contradiction = scores.get("contradiction", 0.0)
            normalized_language = detect_language(original_text, "auto")
            latency_ms = round((perf_counter() - started) * 1000, 3)
            if (
                entailment >= self.entailment_threshold
                and entailment >= contradiction
            ):
                result = ValidationResult(
                    status=SafetyStatus.PASS,
                    risk_score=0.0,
                    risk_level=RiskLevel.LOW,
                    violations=[],
                    warnings=["SEMANTIC_VERIFIER_USED"],
                    recommended_action=RecommendedAction.ACCEPT_CANDIDATE,
                    normalized_language=normalized_language,
                    latency_ms=latency_ms,
                    reason_codes=["SEMANTIC_ENTAILMENT"],
                )
            elif (
                contradiction >= self.entailment_threshold
                and contradiction > entailment
            ):
                result = ValidationResult(
                    status=SafetyStatus.FAIL,
                    risk_score=0.98,
                    risk_level=RiskLevel.CRITICAL,
                    violations=[
                        Violation(
                            code="SEMANTIC_CONTRADICTION",
                            severity=RiskLevel.CRITICAL,
                            category="semantic",
                            message="Optional semantic verifier found a contradiction.",
                            evidence={
                                "entailment": entailment,
                                "contradiction": contradiction,
                                "model_id": self.model_id,
                                "model_revision": self.model_revision,
                            },
                            confidence=contradiction,
                        )
                    ],
                    warnings=["SEMANTIC_VERIFIER_USED"],
                    recommended_action=RecommendedAction.USE_ORIGINAL,
                    normalized_language=normalized_language,
                    latency_ms=latency_ms,
                    reason_codes=["SEMANTIC_CONTRADICTION"],
                )
            else:
                result = ValidationResult(
                    status=SafetyStatus.UNCERTAIN,
                    risk_score=0.35,
                    risk_level=RiskLevel.MEDIUM,
                    violations=[],
                    warnings=["SEMANTIC_LOW_CONFIDENCE"],
                    recommended_action=RecommendedAction.USE_ORIGINAL,
                    normalized_language=normalized_language,
                    latency_ms=latency_ms,
                    reason_codes=["SEMANTIC_LOW_CONFIDENCE"],
                )
            return SemanticVerification(available=True, result=result)
        except Exception as exc:
            del exc
            return SemanticVerification(
                available=False,
                result=None,
                warning="SEMANTIC_VERIFIER_ERROR",
            )
