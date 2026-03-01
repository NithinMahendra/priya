from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "Critical"
    high = "High"
    medium = "Medium"
    low = "Low"


class ReviewIssue(BaseModel):
    line: int | None = None
    type: str
    severity: Severity
    message: str
    suggested_fix: str
    source: str = "local"


class ReviewSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    score: int = 100


class RefactorSuggestion(BaseModel):
    before: str
    after: str
    reason: str


class ReviewRequest(BaseModel):
    code: str = Field(min_length=1)
    filename: str | None = None
    language: str = "python"
    include_project_context: bool = False
    context_text: str | None = None
    dependency_manifest: str | None = None
    manifest_type: str | None = None


class ReviewResponse(BaseModel):
    issues: list[ReviewIssue]
    summary: ReviewSummary
    technical_debt: str
    overall_assessment: str
    refactor_suggestions: list[RefactorSuggestion] = Field(default_factory=list)


class ReviewRunResponse(ReviewResponse):
    submission_id: int
    created_at: datetime
    provider: str


class SubmissionResult(BaseModel):
    id: int
    filename: str | None
    language: str
    quality_score: int
    created_at: datetime
    review_result: dict[str, Any]

    model_config = {"from_attributes": True}


class ScorePoint(BaseModel):
    created_at: datetime
    score: int


class DashboardMetrics(BaseModel):
    issue_distribution: dict[str, int]
    score_trend: list[ScorePoint]
    submissions: int
    average_score: float
