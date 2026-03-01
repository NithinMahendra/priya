export type Severity = "Critical" | "High" | "Medium" | "Low";

export interface ReviewIssue {
  line: number | null;
  type: string;
  severity: Severity;
  message: string;
  suggested_fix: string;
  source: string;
}

export interface ReviewSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  score: number;
}

export interface RefactorSuggestion {
  before: string;
  after: string;
  reason: string;
}

export interface ReviewResponse {
  issues: ReviewIssue[];
  summary: ReviewSummary;
  technical_debt: string;
  overall_assessment: string;
  refactor_suggestions: RefactorSuggestion[];
  provider: string;
  submission_id: number;
  created_at: string;
}

export interface ReviewRequest {
  code: string;
  filename?: string;
  language: string;
}

export interface ScorePoint {
  created_at: string;
  score: number;
}

export interface DashboardMetrics {
  issue_distribution: Record<Severity, number>;
  score_trend: ScorePoint[];
  submissions: number;
  average_score: number;
}
