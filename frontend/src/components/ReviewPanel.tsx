import { DiffEditor } from "@monaco-editor/react";
import { useEffect, useMemo, useState } from "react";

import type { RefactorSuggestion, ReviewIssue, ReviewResponse } from "../types/review";
import { IssueList, issueKey } from "./IssueList";

interface ReviewPanelProps {
  result: ReviewResponse | null;
  loading: boolean;
  error: string | null;
  theme: "dark" | "light";
  onApplyFix: (suggestion: RefactorSuggestion, index: number) => void;
  onIgnoreFix: (suggestion: RefactorSuggestion, index: number) => void;
  onAcceptIssue: (issue: ReviewIssue, index: number) => void;
  onIgnoreIssue: (issue: ReviewIssue, index: number) => void;
  issueDecisions: Record<string, "accepted" | "ignored">;
  fixDecisions: Record<string, "accepted" | "ignored">;
}

function fixKey(item: RefactorSuggestion, index: number): string {
  return `${item.before}:${item.after}:${index}`;
}

function downloadReport(result: ReviewResponse) {
  const file = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(file);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `review-report-${result.submission_id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ReviewPanel({
  result,
  loading,
  error,
  theme,
  onApplyFix,
  onIgnoreFix,
  onAcceptIssue,
  onIgnoreIssue,
  issueDecisions,
  fixDecisions
}: ReviewPanelProps): JSX.Element {
  const [selectedFixIndex, setSelectedFixIndex] = useState(0);

  useEffect(() => {
    setSelectedFixIndex(0);
  }, [result?.submission_id]);

  const selectedFix = useMemo(
    () => (result?.refactor_suggestions ?? [])[selectedFixIndex] ?? null,
    [result, selectedFixIndex]
  );

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-app-border bg-app-panel p-6 shadow-panel">
        <div className="flex items-center gap-3 text-app-muted">
          <span className="size-4 animate-spin rounded-full border-2 border-app-muted border-t-app-accent" />
          Running analysis...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
        {error}
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-app-border bg-app-panel p-6 shadow-panel">
        <p className="text-sm text-app-muted">
          Submit code from the left editor to see issue severity, score, and refactor suggestions.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-4 rounded-2xl border border-app-border bg-app-panel p-5 shadow-panel">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-app-border bg-app-panelSoft p-4">
          <p className="text-xs uppercase tracking-wider text-app-muted">Health Score</p>
          <p className="mt-2 text-3xl font-semibold text-app-text">{result.summary.score}</p>
        </div>
        <div className="rounded-2xl border border-app-border bg-app-panelSoft p-4">
          <p className="text-xs uppercase tracking-wider text-app-muted">Technical Debt</p>
          <p className="mt-2 text-xl font-semibold text-app-text">{result.technical_debt}</p>
          <p className="mt-1 text-xs text-app-muted">Provider: {result.provider}</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 text-sm">
        <Stat label="Critical" value={result.summary.critical} tone="text-red-300" />
        <Stat label="High" value={result.summary.high} tone="text-orange-300" />
        <Stat label="Medium" value={result.summary.medium} tone="text-amber-300" />
        <Stat label="Low" value={result.summary.low} tone="text-emerald-300" />
      </div>

      <article className="rounded-2xl border border-app-border bg-app-panelSoft p-4">
        <p className="text-xs uppercase tracking-wider text-app-muted">Assessment</p>
        <p className="mt-2 text-sm text-app-text">{result.overall_assessment}</p>
        {result.provider === "mock" && (
          <p className="mt-2 text-xs text-amber-300">
            Mock provider is active. Configure OpenRouter to get full semantic analysis quality.
          </p>
        )}
      </article>

      <IssueList
        issues={result.issues}
        decisions={issueDecisions}
        onAcceptIssue={onAcceptIssue}
        onIgnoreIssue={onIgnoreIssue}
      />

      {result.refactor_suggestions.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-app-text">Fix-it Suggestions</h3>

          <div className="grid grid-cols-1 gap-3">
            {result.refactor_suggestions.slice(0, 8).map((item, idx) => {
              const key = fixKey(item, idx);
              const decision = fixDecisions[key];
              return (
                <article
                  key={key}
                  className="rounded-2xl border border-app-border bg-app-panelSoft p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedFixIndex(idx)}
                      className="text-left text-sm text-app-text transition hover:text-white"
                    >
                      Suggestion {idx + 1}
                    </button>
                    {decision ? (
                      <span className="rounded-lg border border-app-border px-2 py-1 text-xs text-app-muted">
                        {decision}
                      </span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => onApplyFix(item, idx)}
                          className="rounded-lg border border-app-border px-2 py-1 text-xs text-emerald-300 transition hover:border-emerald-400/50"
                        >
                          Apply Fix
                        </button>
                        <button
                          type="button"
                          onClick={() => onIgnoreFix(item, idx)}
                          className="rounded-lg border border-app-border px-2 py-1 text-xs text-amber-300 transition hover:border-amber-400/50"
                        >
                          Ignore
                        </button>
                      </div>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-app-muted">{item.reason}</p>
                </article>
              );
            })}
          </div>

          {selectedFix && (
            <div className="overflow-hidden rounded-2xl border border-app-border">
              <div className="border-b border-app-border bg-app-panelSoft px-3 py-2 text-xs text-app-muted">
                {"Side-by-side diff (original -> suggested)"}
              </div>
              <DiffEditor
                height="220px"
                language="plaintext"
                original={selectedFix.before}
                modified={selectedFix.after}
                theme={theme === "dark" ? "vs-dark" : "light"}
                options={{
                  readOnly: true,
                  renderSideBySide: true,
                  minimap: { enabled: false },
                  fontSize: 13,
                  scrollBeyondLastLine: false
                }}
              />
            </div>
          )}
        </section>
      )}

      <button
        type="button"
        onClick={() => downloadReport(result)}
        className="rounded-xl border border-app-border px-4 py-2 text-sm text-app-text transition hover:border-app-accent"
      >
        Download JSON Report
      </button>
    </section>
  );
}

interface StatProps {
  label: string;
  value: number;
  tone: string;
}

function Stat({ label, value, tone }: StatProps): JSX.Element {
  return (
    <div className="rounded-xl border border-app-border bg-app-panelSoft p-3">
      <p className="text-xs text-app-muted">{label}</p>
      <p className={`text-lg font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

export { fixKey, issueKey };
