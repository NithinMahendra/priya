from app.services.llm_provider import MockProvider, OpenAIProvider, build_provider


def test_provider_falls_back_to_mock_when_key_missing() -> None:
    provider = build_provider(provider_name="openai", api_key=None, model="gpt-4.1-mini")
    assert isinstance(provider, MockProvider)


def test_provider_uses_openai_when_key_present() -> None:
    provider = build_provider(
        provider_name="openai",
        api_key="test-key",
        model="gpt-4.1-mini",
    )
    assert isinstance(provider, OpenAIProvider)
