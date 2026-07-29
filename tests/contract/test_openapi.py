from fastapi.testclient import TestClient

from context_guard.api.app import app


def test_openapi_contains_v1_contract() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]
    assert set(("/v1/health", "/v1/capabilities", "/v1/analyze", "/v1/validate")) <= set(paths)
    assert "ValidationResult" in schema["components"]["schemas"]
