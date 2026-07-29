from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from context_guard import __version__
from context_guard.core.guard import ContextGuard
from context_guard.schemas.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CapabilityResponse,
    ErrorBody,
    ErrorResponse,
    GuardConfig,
    HealthResponse,
    ValidateRequest,
    ValidationResult,
)

API_VERSION = "v1"


def create_app() -> FastAPI:
    application = FastAPI(
        title="ContextGuard", version=__version__, description="Offline context safety validation"
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(code="INVALID_REQUEST", message=str(exc), retryable=False)
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @application.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            package_version=__version__,
            api_version=API_VERSION,
            adapters={"semantic": False, "compressors": True},
        )

    @application.get("/v1/capabilities", response_model=CapabilityResponse)
    async def capabilities() -> CapabilityResponse:
        return CapabilityResponse(
            api_version=API_VERSION,
            package_version=__version__,
            languages=["vi", "en", "auto"],
            profiles=["general", "academic", "business", "technical"],
            policies=["lenient", "balanced", "strict"],
            validators=["ExactGuard", "LogicGuard", "EntityGuard", "RelationGuard"],
            semantic_verifier_available=False,
            compressor_adapters=[
                "rule-based",
                "controlled-mutation",
                "token-level-unavailable",
                "llm-summarizer-unavailable",
            ],
            max_input_chars=GuardConfig().max_input_chars,
        )

    @application.post("/v1/analyze", response_model=AnalyzeResponse)
    async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
        config = GuardConfig(language=request.language, profile=request.profile)
        return ContextGuard(config).analyze(request.text)

    @application.post("/v1/validate", response_model=ValidationResult)
    async def validate(request: ValidateRequest) -> ValidationResult:
        config = GuardConfig(
            language=request.language, profile=request.profile, policy=request.policy
        )
        return ContextGuard(config).validate(request.original_text, request.candidate_text)

    @application.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(code="INPUT_INVALID", message=str(exc), retryable=False)
        )
        return JSONResponse(status_code=400, content=body.model_dump(mode="json"))

    return application


app = create_app()
