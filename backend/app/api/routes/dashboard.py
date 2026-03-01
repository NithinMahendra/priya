from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.submission import Submission
from app.models.user import User
from app.schemas.review import DashboardMetrics, ScorePoint

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardMetrics:
    submissions = (
        db.query(Submission)
        .filter(Submission.user_id == current_user.id)
        .order_by(Submission.created_at.asc())
        .all()
    )

    distribution = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    score_trend: list[ScorePoint] = []
    total_score = 0

    for submission in submissions:
        result = submission.review_result or {}
        for issue in result.get("issues", []):
            severity = str(issue.get("severity", "Low"))
            if severity in distribution:
                distribution[severity] += 1
        score = int(result.get("summary", {}).get("score", submission.quality_score))
        score_trend.append(ScorePoint(created_at=submission.created_at, score=score))
        total_score += score

    submission_count = len(submissions)
    average = (total_score / submission_count) if submission_count else 0.0

    return DashboardMetrics(
        issue_distribution=distribution,
        score_trend=score_trend[-20:],
        submissions=submission_count,
        average_score=round(average, 2),
    )
