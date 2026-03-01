from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.integrations import GitHubMockRequest, GitHubMockResponse
from app.services.github_integration import GitHubPRIntegrationMock

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/github/mock-pr", response_model=GitHubMockResponse)
def post_mock_pr_review(
    payload: GitHubMockRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GitHubMockResponse:
    _ = current_user
    integration = GitHubPRIntegrationMock()
    response = integration.post_review_comments(
        repo=payload.repo,
        pr_number=payload.pr_number,
        issues=payload.issues,
    )
    return GitHubMockResponse(**response)
