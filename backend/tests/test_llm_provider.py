import pytest

from app.services.llm_provider import MockProvider, OpenRouterProvider, build_provider


def test_provider_uses_mock_when_configured() -> None:
    provider = build_provider(
        provider_name="mock",
        openrouter_api_key=None,
        model="auto",
    )
    assert isinstance(provider, MockProvider)


def test_provider_requires_openrouter_key_when_configured() -> None:
    with pytest.raises(ValueError):
        build_provider(
            provider_name="openrouter",
            openrouter_api_key=None,
            model="auto",
        )


def test_provider_uses_openrouter_when_key_present() -> None:
    provider = build_provider(
        provider_name="openrouter",
        openrouter_api_key="or-test-key",
        model="auto",
    )
    assert isinstance(provider, OpenRouterProvider)


def test_provider_auto_uses_openrouter_when_key_present() -> None:
    provider = build_provider(
        provider_name="auto",
        openrouter_api_key="or-test-key",
        model="auto",
    )
    assert isinstance(provider, OpenRouterProvider)


def test_provider_auto_uses_mock_when_key_absent() -> None:
    provider = build_provider(
        provider_name="auto",
        openrouter_api_key=None,
        model="auto",
    )
    assert isinstance(provider, MockProvider)


def test_provider_keeps_explicit_model_name() -> None:
    provider = build_provider(
        provider_name="openrouter",
        openrouter_api_key="or-test-key",
        model="qwen/qwen3-coder:free",
    )
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "qwen/qwen3-coder:free"
