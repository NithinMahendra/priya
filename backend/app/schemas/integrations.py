from pydantic import BaseModel, Field


class GitHubMockRequest(BaseModel):
    repo: str = Field(examples=["org/repository"])
    pr_number: int = Field(gt=0)
    issues: list[dict]


class GitHubMockComment(BaseModel):
    path: str
    line: int
    body: str


class GitHubMockResponse(BaseModel):
    status: str
    repo: str
    pr_number: int
    posted_comments: int
    comments: list[GitHubMockComment]
