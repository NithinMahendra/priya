import pytest

from app.services.ai_reviewer import AIReviewer
from app.services.llm_provider import LLMProvider


class FlakyProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def analyze_code(self, code: str, language: str = "python", context: str | None = None):
        self.calls += 1
        if self.calls < 2:
            raise RuntimeError("transient failure")
        return {
            "issues": [
                {
                    "line": 1,
                    "type": "Security",
                    "severity": "High",
                    "message": "Test issue",
                    "suggested_fix": "Fix it",
                    "source": "ai",
                }
            ],
            "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0, "score": 85},
            "technical_debt": "Moderate",
            "overall_assessment": "Needs updates",
            "refactor_suggestions": [],
        }


@pytest.mark.asyncio
async def test_ai_reviewer_retries_before_fallback() -> None:
    provider = FlakyProvider()
    reviewer = AIReviewer(provider=provider)
    result = await reviewer.review(code="print(1)")
    assert result["provider"] == "flaky"
    assert provider.calls >= 2
