import pytest

from app.services.learning_service import LearningService
from app.services.llm_provider import MockProvider


def test_learning_service_infers_sql_injection_concept() -> None:
    service = LearningService(provider=MockProvider())
    concept = service.infer_concept(
        [{"type": "Security", "message": "Possible SQL injection pattern in dynamic SQL construction."}]
    )
    assert concept == "SQL Injection Prevention"


@pytest.mark.asyncio
async def test_learning_service_generates_three_questions() -> None:
    service = LearningService(provider=MockProvider())
    result = await service.generate_quiz("SQL Injection Prevention")
    assert "questions" in result
    assert len(result["questions"]) == 3
    assert all(len(item["options"]) == 4 for item in result["questions"])
