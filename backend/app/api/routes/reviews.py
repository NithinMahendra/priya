from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.review_action import ReviewAction
from app.models.submission import Submission
from app.models.user import User
from app.schemas.review_actions import ReviewActionCreate, ReviewActionRead
from app.schemas.review import ReviewRequest, ReviewRunResponse, SubmissionResult
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/run", response_model=ReviewRunResponse, status_code=status.HTTP_201_CREATED)
async def run_review(
    payload: ReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewRunResponse:
    try:
        review_service = ReviewService()
        result = await review_service.run(
            code=payload.code,
            language=payload.language,
            filename=payload.filename,
            include_project_context=payload.include_project_context,
            context_text=payload.context_text,
            dependency_manifest=payload.dependency_manifest,
            manifest_type=payload.manifest_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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


@router.post("/{submission_id}/actions", response_model=ReviewActionRead, status_code=status.HTTP_201_CREATED)
def create_review_action(
    submission_id: int,
    payload: ReviewActionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewActionRead:
    submission = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.user_id == current_user.id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")

    action = ReviewAction(
        submission_id=submission_id,
        user_id=current_user.id,
        action_type=payload.action_type.value,
        item_key=payload.item_key,
        payload=payload.payload,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


@router.get("/{submission_id}/actions", response_model=list[ReviewActionRead])
def list_review_actions(
    submission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ReviewActionRead]:
    submission = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.user_id == current_user.id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")

    rows = (
        db.query(ReviewAction)
        .filter(ReviewAction.submission_id == submission_id, ReviewAction.user_id == current_user.id)
        .order_by(ReviewAction.created_at.asc())
        .all()
    )
    return rows
