import type {
  DashboardMetrics,
  LearningQuizRequest,
  LearningQuizResponse,
  LearningQuizSubmitRequest,
  LearningQuizSubmitResponse,
  ReviewAction,
  ReviewActionType,
  ReviewRequest,
  ReviewResponse
} from "../types/review";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

type HttpMethod = "GET" | "POST";

async function request<T>(
  path: string,
  method: HttpMethod,
  body?: unknown,
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body && !(body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
  } else if (body instanceof URLSearchParams) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body
        ? body instanceof URLSearchParams
          ? body.toString()
          : JSON.stringify(body)
        : undefined
    });
  } catch (error) {
    const suffix = path.startsWith("/") ? path : `/${path}`;
    const endpoint = `${API_BASE}${suffix}`;
    throw new Error(`Network error: cannot reach backend at ${endpoint}.`);
  }

  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(data.detail ?? `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function register(username: string, password: string): Promise<void> {
  await request("/auth/register", "POST", { username, password });
}

export async function login(username: string, password: string): Promise<string> {
  const tokenResponse = await request<{ access_token: string }>("/auth/login", "POST", {
    username,
    password
  });
  return tokenResponse.access_token;
}

export async function getCurrentUser(
  token: string
): Promise<{ id: number; username: string; quiz_score: number; created_at: string }> {
  return request<{ id: number; username: string; quiz_score: number; created_at: string }>(
    "/auth/me",
    "GET",
    undefined,
    token
  );
}

export async function runReview(
  payload: ReviewRequest,
  token: string
): Promise<ReviewResponse> {
  return request<ReviewResponse>("/reviews/run", "POST", payload, token);
}

export async function getDashboardMetrics(token: string): Promise<DashboardMetrics> {
  return request<DashboardMetrics>("/dashboard/metrics", "GET", undefined, token);
}

export async function listReviewActions(submissionId: number, token: string): Promise<ReviewAction[]> {
  return request<ReviewAction[]>(`/reviews/${submissionId}/actions`, "GET", undefined, token);
}

export async function createReviewAction(
  submissionId: number,
  payload: { action_type: ReviewActionType; item_key: string; payload: Record<string, unknown> },
  token: string
): Promise<ReviewAction> {
  return request<ReviewAction>(`/reviews/${submissionId}/actions`, "POST", payload, token);
}

export async function generateLearningQuiz(
  payload: LearningQuizRequest,
  token: string
): Promise<LearningQuizResponse> {
  return request<LearningQuizResponse>("/learning/quiz/generate", "POST", payload, token);
}

export async function submitLearningQuiz(
  payload: LearningQuizSubmitRequest,
  token: string
): Promise<LearningQuizSubmitResponse> {
  return request<LearningQuizSubmitResponse>("/learning/quiz/submit", "POST", payload, token);
}
