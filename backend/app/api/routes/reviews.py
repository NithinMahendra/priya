from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.submission import Submission
from app.models.user import User
from app.schemas.review import ReviewRequest, ReviewRunResponse, SubmissionResult
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/run", response_model=ReviewRunResponse, status_code=status.HTTP_201_CREATED)
async def run_review(
    payload: ReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewRunResponse:
    review_service = ReviewService()
    result = await review_service.run(code=payload.code, language=payload.language)

    submission = Submission(
        user_id=current_user.id,
        filename=payload.filename,
        language=payload.language,
        code_text=payload.code,
        review_result=result,
        quality_score=result["summary"]["score"],
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return ReviewRunResponse(
        submission_id=submission.id,
        created_at=submission.created_at,
        provider=result["provider"],
        issues=result["issues"],
        summary=result["summary"],
        technical_debt=result["technical_debt"],
        overall_assessment=result["overall_assessment"],
        refactor_suggestions=result["refactor_suggestions"],
    )


@router.get("/{submission_id}", response_model=SubmissionResult)
def get_submission(
    submission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubmissionResult:
    submission = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.user_id == current_user.id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return submission


@router.get("", response_model=list[SubmissionResult])
def list_submissions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SubmissionResult]:
    rows = (
        db.query(Submission)
        .filter(Submission.user_id == current_user.id)
        .order_by(Submission.created_at.desc())
        .limit(50)
        .all()
    )
    return rows
