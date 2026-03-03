import { useMemo, useState } from "react";

import { generateLearningQuiz, submitLearningQuiz } from "../api/client";
import { TopBar } from "../components/TopBar";
import type { LearningQuizResponse } from "../types/review";

interface LearningHubProps {
  token: string | null;
  username: string | null;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
}

const STORAGE_SUBMISSION_KEY = "learning:last_submission_id";

export function LearningHub({
  token,
  username,
  theme,
  onToggleTheme,
  onLogin,
  onRegister,
  onLogout,
}: LearningHubProps): JSX.Element {
  const [concept, setConcept] = useState("");
  const [submissionId, setSubmissionId] = useState(() => localStorage.getItem(STORAGE_SUBMISSION_KEY) ?? "");
  const [quiz, setQuiz] = useState<LearningQuizResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quizScore, setQuizScore] = useState<number | null>(null);

  const answeredCount = useMemo(() => Object.keys(answers).length, [answers]);

  const requestQuiz = async (mode: "concept" | "submission") => {
    if (!token) {
      setError("Authentication required. Login to generate quizzes.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload =
        mode === "submission"
          ? { submission_id: Number(submissionId) || undefined }
          : { concept: concept.trim() || undefined };
      const result = await generateLearningQuiz(payload, token);
      setQuiz(result);
      setAnswers({});
      setQuizScore(null);
      if (submissionId) {
        localStorage.setItem(STORAGE_SUBMISSION_KEY, submissionId);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to generate quiz.");
    } finally {
      setLoading(false);
    }
  };

  const submitQuiz = async () => {
    if (!token || !quiz) {
      return;
    }
    const total = quiz.questions.length;
    const score = quiz.questions.reduce((sum, question, index) => {
      return sum + (answers[index] === question.correct_option ? 1 : 0);
    }, 0);

    setSubmitting(true);
    setError(null);
    try {
      const response = await submitLearningQuiz({ score, total }, token);
      setQuizScore(response.quiz_score);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to submit quiz.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <TopBar
        active="learning"
        theme={theme}
        onToggleTheme={onToggleTheme}
        token={token}
        username={username}
        onLogin={onLogin}
        onRegister={onRegister}
        onLogout={onLogout}
      />

      <main className="mx-auto max-w-[1200px] space-y-5 px-6 py-6">
        {!token && (
          <section className="rounded-2xl border border-app-border bg-app-panel p-5 text-sm text-app-muted shadow-panel">
            Login to generate educational quizzes from your review findings.
          </section>
        )}

        <section className="rounded-2xl border border-app-border bg-app-panel p-5 shadow-panel">
          <h2 className="text-sm font-semibold text-app-text">Quiz Generator</h2>
          <p className="mt-1 text-xs text-app-muted">
            Generate 3 MCQs from a concept or from the latest reviewed submission.
          </p>

          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-xs text-app-muted">Concept</label>
              <input
                value={concept}
                onChange={(event) => setConcept(event.target.value)}
                placeholder="SQL Injection Prevention"
                className="w-full rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:border-app-accent focus:outline-none"
              />
              <button
                type="button"
                disabled={loading || !token}
                onClick={() => void requestQuiz("concept")}
                className="rounded-xl border border-app-border px-3 py-2 text-xs text-app-text transition hover:border-app-accent disabled:opacity-60"
              >
                Generate from Concept
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-app-muted">Submission ID</label>
              <input
                value={submissionId}
                onChange={(event) => setSubmissionId(event.target.value)}
                placeholder="e.g., 42"
                className="w-full rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:border-app-accent focus:outline-none"
              />
              <button
                type="button"
                disabled={loading || !token || !submissionId}
                onClick={() => void requestQuiz("submission")}
                className="rounded-xl border border-app-border px-3 py-2 text-xs text-app-text transition hover:border-app-accent disabled:opacity-60"
              >
                Generate from Submission
              </button>
            </div>
          </div>
        </section>

        {loading && (
          <section className="rounded-2xl border border-app-border bg-app-panel p-4 text-sm text-app-muted shadow-panel">
            Generating quiz...
          </section>
        )}

        {error && (
          <section className="rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </section>
        )}

        {quiz && (
          <section className="space-y-4 rounded-2xl border border-app-border bg-app-panel p-5 shadow-panel">
            <div className="rounded-xl border border-app-border bg-app-panelSoft p-3">
              <p className="text-xs uppercase tracking-wide text-app-muted">Concept</p>
              <p className="mt-1 text-sm text-app-text">{quiz.concept}</p>
              <p className="mt-1 text-xs text-app-muted">Source: {quiz.source}</p>
            </div>

            {quiz.questions.map((question, questionIndex) => (
              <article key={questionIndex} className="rounded-xl border border-app-border bg-app-panelSoft p-4">
                <p className="text-sm font-medium text-app-text">
                  Q{questionIndex + 1}. {question.question}
                </p>
                <div className="mt-3 space-y-2">
                  {question.options.map((option, optionIndex) => (
                    <label key={optionIndex} className="flex cursor-pointer items-center gap-2 text-sm text-app-text">
                      <input
                        type="radio"
                        name={`q-${questionIndex}`}
                        checked={answers[questionIndex] === optionIndex}
                        onChange={() =>
                          setAnswers((prev) => ({
                            ...prev,
                            [questionIndex]: optionIndex,
                          }))
                        }
                      />
                      <span>{option}</span>
                    </label>
                  ))}
                </div>
              </article>
            ))}

            <div className="flex items-center justify-between">
              <span className="text-xs text-app-muted">
                Answered {answeredCount}/{quiz.questions.length}
              </span>
              <button
                type="button"
                disabled={submitting || answeredCount < quiz.questions.length}
                onClick={() => void submitQuiz()}
                className="rounded-xl bg-app-accent px-4 py-2 text-sm font-semibold text-slate-900 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-65"
              >
                {submitting ? "Submitting..." : "Submit Quiz"}
              </button>
            </div>

            {quizScore !== null && (
              <p className="text-sm text-emerald-300">Quiz submitted. Total Learning Score: {quizScore}</p>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
