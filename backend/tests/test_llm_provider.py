import pytest

from app.services.llm_provider import GroqProvider, MockProvider, OpenRouterProvider, build_provider


def test_provider_uses_mock_when_configured() -> None:
    provider = build_provider(
        provider_name="mock",
        groq_api_key=None,
        openrouter_api_key=None,
        model="auto",
    )
    assert isinstance(provider, MockProvider)


def test_provider_requires_groq_key_when_configured() -> None:
    with pytest.raises(ValueError):
        build_provider(
            provider_name="groq",
            groq_api_key=None,
            openrouter_api_key=None,
            model="llama-3.3-70b-versatile",
        )


def test_provider_requires_openrouter_key_when_configured() -> None:
    with pytest.raises(ValueError):
        build_provider(
            provider_name="openrouter",
            groq_api_key=None,
            openrouter_api_key=None,
            model="auto",
        )


def test_provider_uses_groq_when_key_present() -> None:
    provider = build_provider(
        provider_name="groq",
        groq_api_key="gsk-test-key",
        openrouter_api_key=None,
        model="llama-3.3-70b-versatile",
    )
    assert isinstance(provider, GroqProvider)


def test_provider_uses_openrouter_when_key_present() -> None:
    provider = build_provider(
        provider_name="openrouter",
        groq_api_key=None,
        openrouter_api_key="or-test-key",
        model="auto",
    )
    assert isinstance(provider, OpenRouterProvider)


def test_provider_auto_prefers_groq_when_key_present() -> None:
    provider = build_provider(
        provider_name="auto",
        groq_api_key="gsk-test-key",
        openrouter_api_key="or-test-key",
        model="llama-3.3-70b-versatile",
    )
    assert isinstance(provider, GroqProvider)


def test_provider_auto_uses_openrouter_when_only_openrouter_key_present() -> None:
    provider = build_provider(
        provider_name="auto",
        groq_api_key=None,
        openrouter_api_key="or-test-key",
        model="auto",
    )
    assert isinstance(provider, OpenRouterProvider)


def test_provider_auto_uses_mock_when_keys_absent() -> None:
    provider = build_provider(
        provider_name="auto",
        groq_api_key=None,
        openrouter_api_key=None,
        model="auto",
    )
    assert isinstance(provider, MockProvider)


def test_provider_keeps_explicit_model_name() -> None:
    provider = build_provider(
        provider_name="groq",
        groq_api_key="gsk-test-key",
        openrouter_api_key=None,
        model="llama-3.3-70b-versatile",
    )
    assert isinstance(provider, GroqProvider)
    assert provider.model == "llama-3.3-70b-versatile"


def test_provider_accepts_openrouter_latency_controls() -> None:
    provider = build_provider(
        provider_name="openrouter",
        groq_api_key=None,
        openrouter_api_key="or-test-key",
        model="auto",
        timeout_seconds=9.0,
        total_timeout_seconds=13.0,
        max_candidates=2,
    )
    assert isinstance(provider, OpenRouterProvider)
    assert provider.timeout_seconds == 9.0
    assert provider.total_timeout_seconds == 13.0
    assert provider.max_candidates == 2


@pytest.mark.asyncio
async def test_explicit_free_model_skips_catalog_lookup() -> None:
    model_id = "nvidia/nemotron-3-nano-30b-a3b:free"
    provider = OpenRouterProvider(
        api_key="or-test-key",
        model=model_id,
        free_only=True,
    )

    async def should_not_call() -> list[dict[str, object]]:
        raise AssertionError("catalog lookup should be skipped for explicit :free models")

    provider._get_models = should_not_call  # type: ignore[method-assign]
    candidates = await provider._pick_candidate_models(needed_tokens=512)
    assert candidates == [model_id]
