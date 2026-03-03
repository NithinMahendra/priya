import pytest

from app.services.review_service import ReviewService


class QuotaFailingAIReviewer:
    async def review(self, code: str, language: str = "python", context: str | None = None):
        _ = code
        _ = language
        _ = context
        raise RuntimeError(
            "LLM provider failed after retries and mock fallback is disabled. "
            "Cause: OpenRouter failed across candidate models for review. Tried 1 models. "
            "Details: nvidia/nemotron-3-nano-30b-a3b:free: Rate limit exceeded: free-models-per-day. "
            "Add 10 credits to unlock 1000 free model requests per day (code=429)"
        )


@pytest.mark.asyncio
async def test_review_service_returns_local_analysis_on_openrouter_quota() -> None:
    code = "def f(x):\n    return eval(x)\n"
    service = ReviewService(ai_reviewer=QuotaFailingAIReviewer())  # type: ignore[arg-type]
    result = await service.run(code=code, language="python")

    assert result["provider"].startswith("openrouter-quota-degraded")
    assert isinstance(result["issues"], list)
    assert any(issue["source"] == "security" for issue in result["issues"])
    assert "Local-only analysis completed" in result["overall_assessment"]
