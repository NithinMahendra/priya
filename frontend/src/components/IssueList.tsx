import type { ReviewIssue } from "../types/review";
import { SeverityBadge } from "./SeverityBadge";

type IssueDecision = "accepted" | "ignored";

interface IssueListProps {
  issues: ReviewIssue[];
  decisions?: Record<string, IssueDecision>;
  onAcceptIssue?: (issue: ReviewIssue, index: number) => void;
  onIgnoreIssue?: (issue: ReviewIssue, index: number) => void;
  onViewFix?: (issue: ReviewIssue, index: number) => void;
}

export function issueKey(issue: ReviewIssue, index: number): string {
  return `${issue.type}:${issue.line ?? "na"}:${issue.message}:${index}`;
}

export function IssueList({
  issues,
  decisions = {},
  onAcceptIssue,
  onIgnoreIssue,
  onViewFix
}: IssueListProps): JSX.Element {
  if (!issues.length) {
    return (
      <div className="rounded-2xl border border-app-border bg-app-panelSoft p-4 text-sm text-app-muted">
        No issues were reported.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {issues.map((issue, idx) => {
        const key = issueKey(issue, idx);
        const state = decisions[key];
        return (
          <article
            key={key}
            className="rounded-2xl border border-app-border bg-app-panelSoft p-4 shadow-panel"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-app-text">
                {issue.type}
                {issue.line ? ` - Line ${issue.line}` : ""}
              </span>
              <SeverityBadge severity={issue.severity} />
            </div>

            <p className="text-sm text-app-text">{issue.message}</p>
            <p className="mt-2 text-xs text-app-muted">Fix: {issue.suggested_fix}</p>

            <div className="mt-3 flex items-center justify-between gap-3">
              <span className="text-[11px] uppercase tracking-wide text-app-muted">
                Confidence: {issue.confidence ?? "medium"}
              </span>

              <div className="flex items-center gap-2">
                {onViewFix && issue.original_code && issue.fixed_code !== undefined && issue.fixed_code !== null && (
                  <button
                    type="button"
                    onClick={() => onViewFix(issue, idx)}
                    className="rounded-lg border border-app-border px-2 py-1 text-xs text-cyan-300 transition hover:border-cyan-400/50"
                  >
                    View Fix
                  </button>
                )}

                {state ? (
                  <span className="rounded-lg border border-app-border px-2 py-1 text-xs text-app-muted">
                    {state}
                  </span>
                ) : (
                  <>
                    {onAcceptIssue && (
                      <button
                        type="button"
                        onClick={() => onAcceptIssue(issue, idx)}
                        className="rounded-lg border border-app-border px-2 py-1 text-xs text-emerald-300 transition hover:border-emerald-400/50"
                      >
                        Accept
                      </button>
                    )}
                    {onIgnoreIssue && (
                      <button
                        type="button"
                        onClick={() => onIgnoreIssue(issue, idx)}
                        className="rounded-lg border border-app-border px-2 py-1 text-xs text-amber-300 transition hover:border-amber-400/50"
                      >
                        Ignore
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
