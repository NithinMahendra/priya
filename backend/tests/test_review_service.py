import pytest

from app.services.review_service import ReviewService


@pytest.mark.asyncio
async def test_review_service_returns_structured_response() -> None:
    code = """
def process(user_input):
    query = "SELECT * FROM users WHERE name = '" + user_input + "'"
    cursor.execute(query)
    return eval(user_input)
""".strip()
    service = ReviewService()
    result = await service.run(code=code, language="python")

    assert "issues" in result
    assert "summary" in result
    assert "technical_debt" in result
    assert "overall_assessment" in result
    assert "refactor_suggestions" in result
    assert result["summary"]["critical"] >= 1
