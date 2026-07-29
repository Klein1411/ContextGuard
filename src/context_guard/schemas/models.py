from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SafetyStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendedAction(StrEnum):
    ACCEPT_CANDIDATE = "ACCEPT_CANDIDATE"
    RETRY_WITH_LOWER_COMPRESSION = "RETRY_WITH_LOWER_COMPRESSION"
    USE_ORIGINAL = "USE_ORIGINAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class GuardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = "auto"
    profile: str = "general"
    policy: str = "strict"
    max_input_chars: int = Field(default=100_000, ge=1, le=2_000_000)

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        if value not in {"auto", "vi", "en"}:
            raise ValueError("language must be one of: auto, vi, en")
        return value

    @field_validator("profile")
    @classmethod
    def valid_profile(cls, value: str) -> str:
        if value not in {"general", "academic", "business", "technical"}:
            raise ValueError("profile must be one of: general, academic, business, technical")
        return value

    @field_validator("policy")
    @classmethod
    def valid_policy(cls, value: str) -> str:
        if value not in {"lenient", "balanced", "strict"}:
            raise ValueError("policy must be one of: lenient, balanced, strict")
        return value


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    text: str = Field(max_length=100_000)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    normalized_value: str | None = None
    severity: RiskLevel = RiskLevel.MEDIUM
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProtectedSpan(Fact):
    """Fact span exposed to compressor adapters before compression."""


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: RiskLevel
    category: str
    message: str
    original_span: str | None = None
    candidate_span: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    language: str = "auto"
    profile: str = "general"

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        if value not in {"auto", "vi", "en"}:
            raise ValueError("language must be one of: auto, vi, en")
        return value

    @field_validator("profile")
    @classmethod
    def valid_profile(cls, value: str) -> str:
        if value not in {"general", "academic", "business", "technical"}:
            raise ValueError("profile must be one of: general, academic, business, technical")
        return value


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_language: str
    facts: list[Fact]
    protected_spans: list[ProtectedSpan]
    warnings: list[str]
    latency_ms: float


class ValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str = Field(max_length=100_000)
    candidate_text: str = Field(max_length=100_000)
    language: str = "auto"
    profile: str = "general"
    policy: str = "strict"

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        if value not in {"auto", "vi", "en"}:
            raise ValueError("language must be one of: auto, vi, en")
        return value

    @field_validator("profile")
    @classmethod
    def valid_profile(cls, value: str) -> str:
        if value not in {"general", "academic", "business", "technical"}:
            raise ValueError("profile must be one of: general, academic, business, technical")
        return value

    @field_validator("policy")
    @classmethod
    def valid_policy(cls, value: str) -> str:
        if value not in {"lenient", "balanced", "strict"}:
            raise ValueError("policy must be one of: lenient, balanced, strict")
        return value


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SafetyStatus
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    violations: list[Violation]
    warnings: list[str] = Field(default_factory=list)
    recommended_action: RecommendedAction
    normalized_language: str
    latency_ms: float
    reason_codes: list[str] = Field(default_factory=list)


class AnalyzeResult(AnalyzeResponse):
    pass


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorBody


class CapabilityResponse(BaseModel):
    api_version: str
    package_version: str
    languages: list[str]
    profiles: list[str]
    policies: list[str]
    validators: list[str]
    semantic_verifier_available: bool
    compressor_adapters: list[str]
    max_input_chars: int


class HealthResponse(BaseModel):
    status: str
    package_version: str
    api_version: str
    adapters: dict[str, bool]
