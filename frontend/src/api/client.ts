import type {
  DashboardMetrics,
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

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body
      ? body instanceof URLSearchParams
        ? body.toString()
        : JSON.stringify(body)
      : undefined
  });

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
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);
  const tokenResponse = await request<{ access_token: string }>(
    "/auth/token",
    "POST",
    formData
  );
  return tokenResponse.access_token;
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
