import type { ReviewResponse } from "../types/review";
import { IssueList } from "./IssueList";

interface ReviewPanelProps {
  result: ReviewResponse | null;
  loading: boolean;
  error: string | null;
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

export function ReviewPanel({ result, loading, error }: ReviewPanelProps): JSX.Element {
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
          <p className="text-xs uppercase tracking-wider text-app-muted">Quality Score</p>
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
      </article>

      <IssueList issues={result.issues} />

      {result.refactor_suggestions.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold text-app-text">Refactor Suggestions (Before → After)</h3>
          {result.refactor_suggestions.slice(0, 4).map((item, idx) => (
            <article key={`${item.before}-${idx}`} className="rounded-2xl border border-app-border bg-app-panelSoft p-4">
              <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                <pre className="overflow-x-auto rounded-xl bg-black/30 p-3 font-mono text-xs text-red-200">
                  {item.before}
                </pre>
                <pre className="overflow-x-auto rounded-xl bg-black/30 p-3 font-mono text-xs text-emerald-200">
                  {item.after}
                </pre>
              </div>
              <p className="mt-2 text-xs text-app-muted">{item.reason}</p>
            </article>
          ))}
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
