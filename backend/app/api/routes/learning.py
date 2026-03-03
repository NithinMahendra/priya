from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.submission import Submission
from app.models.user import User
from app.schemas.learning import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["learning"])


@router.post("/quiz/generate", response_model=QuizGenerateResponse)
async def generate_quiz(
    payload: QuizGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> QuizGenerateResponse:
    service = LearningService()
    concept = (payload.concept or "").strip()

    if not concept and payload.submission_id:
        submission = (
            db.query(Submission)
            .filter(Submission.id == payload.submission_id, Submission.user_id == current_user.id)
            .first()
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found.")
        review_result = submission.review_result if isinstance(submission.review_result, dict) else {}
        issues = review_result.get("issues", [])
        if not isinstance(issues, list):
            issues = []
        concept = service.infer_concept(issues)

    if not concept:
        raise HTTPException(status_code=400, detail="Provide concept or submission_id.")

    result = await service.generate_quiz(concept)
    return QuizGenerateResponse(**result)


@router.post("/quiz/submit", response_model=QuizSubmitResponse)
def submit_quiz(
    payload: QuizSubmitRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> QuizSubmitResponse:
    score = max(0, min(payload.score, payload.total))
    current_user.quiz_score = int(current_user.quiz_score or 0) + score
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return QuizSubmitResponse(score=score, total=payload.total, quiz_score=current_user.quiz_score)
