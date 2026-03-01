import type { Severity } from "../types/review";

interface SeverityBadgeProps {
  severity: Severity;
}

const severityClass: Record<Severity, string> = {
  Critical: "bg-red-500/20 text-red-300 border-red-400/40",
  High: "bg-orange-500/20 text-orange-300 border-orange-400/40",
  Medium: "bg-amber-500/20 text-amber-300 border-amber-400/40",
  Low: "bg-emerald-500/20 text-emerald-300 border-emerald-400/40"
};

export function SeverityBadge({ severity }: SeverityBadgeProps): JSX.Element {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${severityClass[severity]}`}
    >
      {severity}
    </span>
  );
}
