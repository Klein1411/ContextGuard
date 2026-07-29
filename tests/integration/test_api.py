from fastapi.testclient import TestClient

from context_guard.api.app import app


def test_health_and_capabilities() -> None:
    client = TestClient(app)
    assert client.get("/v1/health").status_code == 200
    body = client.get("/v1/capabilities").json()
    assert body["api_version"] == "v1"
    assert "vi" in body["languages"]
    assert "rule-based" in body["compressor_adapters"]
    assert body["semantic_verifier_available"] is False


def test_validate_uses_contract_schema() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/validate",
        json={
            "original_text": "Must use Python 3.11.",
            "candidate_text": "Must use Python 3.12.",
            "language": "en",
            "profile": "technical",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAIL"
    assert "VERSION_CHANGED" in body["reason_codes"]


def test_invalid_request_has_structured_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/validate", json={"original_text": "x", "candidate_text": "y", "policy": "unknown"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_oversized_request_is_rejected_without_truncation() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/validate", json={"original_text": "x" * 100_001, "candidate_text": "x"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
