export type Severity = "Critical" | "High" | "Medium" | "Low";

export interface ReviewIssue {
  line: number | null;
  type: string;
  severity: Severity;
  message: string;
  suggested_fix: string;
  source: string;
  confidence?: string;
  original_code?: string | null;
  fixed_code?: string | null;
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

export interface PerformanceHotspot {
  line: number | null;
  operation: string;
  estimated_complexity: string;
  recommendation: string;
  source: string;
}

export interface PerformanceProfile {
  time_complexity: string;
  space_complexity: string;
  confidence: "low" | "medium" | "high" | string;
  hotspots: PerformanceHotspot[];
}

export interface ReviewResponse {
  issues: ReviewIssue[];
  summary: ReviewSummary;
  technical_debt: string;
  overall_assessment: string;
  refactor_suggestions: RefactorSuggestion[];
  performance?: PerformanceProfile;
  provider: string;
  submission_id: number;
  created_at: string;
}

export interface ReviewRequest {
  code: string;
  filename?: string;
  language: string;
  include_project_context?: boolean;
  context_text?: string;
  dependency_manifest?: string;
  manifest_type?: string;
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

export type ReviewActionType = "accept_fix" | "ignore_fix" | "accept_issue" | "ignore_issue";

export interface ReviewAction {
  id: number;
  submission_id: number;
  action_type: ReviewActionType;
  item_key: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_option: number;
  explanation: string;
}

export interface LearningQuizResponse {
  concept: string;
  source: string;
  questions: QuizQuestion[];
}

export interface LearningQuizRequest {
  concept?: string;
  submission_id?: number;
}

export interface LearningQuizSubmitRequest {
  score: number;
  total: number;
}

export interface LearningQuizSubmitResponse {
  score: number;
  total: number;
  quiz_score: number;
}
