from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_health_provider_shape() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health/provider")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "provider",
        "effective_provider",
        "model_mode",
        "free_only",
        "api_base_host",
        "mock_fallback_allowed",
    }
    assert payload["provider"] in {"openrouter", "mock"}
    assert payload["effective_provider"] in {"openrouter", "mock"}
    assert isinstance(payload["model_mode"], str) and payload["model_mode"]
    assert isinstance(payload["free_only"], bool)
    assert isinstance(payload["api_base_host"], str) and payload["api_base_host"]
    assert isinstance(payload["mock_fallback_allowed"], bool)


def test_health_provider_does_not_expose_api_key() -> None:
    original = settings.OPENROUTER_API_KEY
    settings.OPENROUTER_API_KEY = "sk-or-v1-test-secret-should-not-leak"
    try:
        client = TestClient(app)
        response = client.get("/api/v1/health/provider")
        assert response.status_code == 200
        payload = response.json()
        serialized = str(payload)
        assert "OPENROUTER_API_KEY" not in serialized
        assert "sk-or-v1" not in serialized
        assert "test-secret-should-not-leak" not in serialized
    finally:
        settings.OPENROUTER_API_KEY = original
