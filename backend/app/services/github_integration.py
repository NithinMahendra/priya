from typing import Any


class GitHubPRIntegrationMock:
    def post_review_comments(
        self,
        repo: str,
        pr_number: int,
        issues: list[dict[str, Any]],
        default_path: str = "src/main.py",
    ) -> dict[str, Any]:
        comments = []
        for issue in issues[:10]:
            comments.append(
                {
                    "path": default_path,
                    "line": int(issue.get("line") or 1),
                    "body": (
                        f"[{issue.get('severity', 'Low')}] {issue.get('message', 'Issue detected.')} "
                        f"Fix: {issue.get('suggested_fix', 'Review this section.')}"
                    ),
                }
            )

        return {
            "status": "mock_posted",
            "repo": repo,
            "pr_number": pr_number,
            "posted_comments": len(comments),
            "comments": comments,
        }
