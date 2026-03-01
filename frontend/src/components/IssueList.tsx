import type { ReviewIssue } from "../types/review";
import { SeverityBadge } from "./SeverityBadge";

interface IssueListProps {
  issues: ReviewIssue[];
}

export function IssueList({ issues }: IssueListProps): JSX.Element {
  if (!issues.length) {
    return (
      <div className="rounded-2xl border border-app-border bg-app-panelSoft p-4 text-sm text-app-muted">
        No issues were reported.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {issues.map((issue, idx) => (
        <article
          key={`${issue.type}-${issue.line ?? "noline"}-${idx}`}
          className="rounded-2xl border border-app-border bg-app-panelSoft p-4 shadow-panel"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold text-app-text">
              {issue.type}
              {issue.line ? ` · Line ${issue.line}` : ""}
            </span>
            <SeverityBadge severity={issue.severity} />
          </div>
          <p className="text-sm text-app-text">{issue.message}</p>
          <p className="mt-2 text-xs text-app-muted">Fix: {issue.suggested_fix}</p>
        </article>
      ))}
    </div>
  );
}
