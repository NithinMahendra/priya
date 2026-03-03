import Editor from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import { useEffect, useMemo, useRef, useState } from "react";

import { createReviewAction, listReviewActions, runReview } from "../api/client";
import { FileUploader } from "../components/FileUploader";
import { fixKey, issueKey, ReviewPanel } from "../components/ReviewPanel";
import { TopBar } from "../components/TopBar";
import type { RefactorSuggestion, ReviewAction, ReviewIssue, ReviewResponse } from "../types/review";

interface ReviewerPageProps {
  token: string | null;
  username: string | null;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
  onReviewCompleted: () => void;
}

const STORAGE_CODE_KEY = "reviewer:last_code";
const STORAGE_FILE_KEY = "reviewer:last_file";
const STORAGE_LANG_KEY = "reviewer:last_language";
const DEFAULT_SAMPLE = `import sqlite3

def get_user(user_input):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + user_input
    cursor.execute(query)
    return eval(user_input)
`;

export function ReviewerPage({
  token,
  username,
  theme,
  onToggleTheme,
  onLogin,
  onRegister,
  onLogout,
  onReviewCompleted
}: ReviewerPageProps): JSX.Element {
  const [code, setCode] = useState(() => localStorage.getItem(STORAGE_CODE_KEY) ?? DEFAULT_SAMPLE);
  const [language, setLanguage] = useState(() => localStorage.getItem(STORAGE_LANG_KEY) ?? "python");
  const [fileName, setFileName] = useState<string | undefined>(
    () => localStorage.getItem(STORAGE_FILE_KEY) ?? "sample.py"
  );
  const [includeProjectContext, setIncludeProjectContext] = useState(false);
  const [contextText, setContextText] = useState("");
  const [result, setResult] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issueDecisions, setIssueDecisions] = useState<Record<string, "accepted" | "ignored">>({});
  const [fixDecisions, setFixDecisions] = useState<Record<string, "accepted" | "ignored">>({});

  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const lineCount = useMemo(() => code.split(/\r?\n/).length, [code]);

  useEffect(() => {
    localStorage.setItem(STORAGE_CODE_KEY, code);
  }, [code]);

  useEffect(() => {
    if (fileName) {
      localStorage.setItem(STORAGE_FILE_KEY, fileName);
    }
  }, [fileName]);

  useEffect(() => {
    localStorage.setItem(STORAGE_LANG_KEY, language);
  }, [language]);

  const run = async () => {
    if (!token) {
      setError("Authentication required. Register or login from the top bar.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await runReview(
        {
          code,
          filename: fileName,
          language,
          include_project_context: includeProjectContext,
          context_text: contextText || undefined
        },
        token
      );
      setResult(response);
      localStorage.setItem("learning:last_submission_id", String(response.submission_id));
      setIssueDecisions({});
      setFixDecisions({});
      onReviewCompleted();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Review failed.");
    } finally {
      setLoading(false);
    }
  };

  const clearPanel = () => {
    setResult(null);
    setError(null);
    setIssueDecisions({});
    setFixDecisions({});
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (editor && monaco) {
      const model = editor.getModel();
      if (model) {
        monaco.editor.setModelMarkers(model, "ai-review", []);
      }
    }
  };

  const persistAction = async (
    actionType: "accept_fix" | "ignore_fix" | "accept_issue" | "ignore_issue",
    itemKey: string,
    payload: Record<string, unknown>
  ) => {
    if (!token || !result) {
      return;
    }
    try {
      await createReviewAction(
        result.submission_id,
        {
          action_type: actionType,
          item_key: itemKey,
          payload
        },
        token
      );
    } catch {
      // Action persistence failures are non-blocking for local UX.
    }
  };

  const handleApplyFix = (suggestion: RefactorSuggestion, index: number) => {
    const replacementTarget = suggestion.before;
    const replacement = suggestion.after;
    let nextCode = code;
    if (replacementTarget && code.includes(replacementTarget)) {
      nextCode = code.replace(replacementTarget, replacement);
    } else {
      nextCode = `${code}\n\n${replacement}`;
    }
    setCode(nextCode);
    const key = fixKey(suggestion, index);
    setFixDecisions((prev) => ({ ...prev, [key]: "accepted" }));
    void persistAction("accept_fix", key, { before: suggestion.before, after: suggestion.after });
  };

  const handleIgnoreFix = (suggestion: RefactorSuggestion, index: number) => {
    const key = fixKey(suggestion, index);
    setFixDecisions((prev) => ({ ...prev, [key]: "ignored" }));
    void persistAction("ignore_fix", key, { before: suggestion.before, after: suggestion.after });
  };

  const handleAcceptIssue = (issue: ReviewIssue, index: number) => {
    const key = issueKey(issue, index);
    setIssueDecisions((prev) => ({ ...prev, [key]: "accepted" }));
    void persistAction("accept_issue", key, issue as unknown as Record<string, unknown>);
  };

  const handleIgnoreIssue = (issue: ReviewIssue, index: number) => {
    const key = issueKey(issue, index);
    setIssueDecisions((prev) => ({ ...prev, [key]: "ignored" }));
    void persistAction("ignore_issue", key, issue as unknown as Record<string, unknown>);
  };

  useEffect(() => {
    if (!token || !result) {
      return;
    }
    const loadActions = async () => {
      try {
        const actions = await listReviewActions(result.submission_id, token);
        hydrateDecisions(actions);
      } catch {
        // If action history load fails, continue with local interaction state only.
      }
    };
    void loadActions();
  }, [token, result?.submission_id]);

  const hydrateDecisions = (actions: ReviewAction[]) => {
    const issueMap: Record<string, "accepted" | "ignored"> = {};
    const fixMap: Record<string, "accepted" | "ignored"> = {};

    for (const action of actions) {
      if (action.action_type === "accept_issue") {
        issueMap[action.item_key] = "accepted";
      } else if (action.action_type === "ignore_issue") {
        issueMap[action.item_key] = "ignored";
      } else if (action.action_type === "accept_fix") {
        fixMap[action.item_key] = "accepted";
      } else if (action.action_type === "ignore_fix") {
        fixMap[action.item_key] = "ignored";
      }
    }
    setIssueDecisions(issueMap);
    setFixDecisions(fixMap);
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const triggerReview = (event.metaKey || event.ctrlKey) && event.key === "Enter";
      if (triggerReview) {
        event.preventDefault();
        void run();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        clearPanel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  useEffect(() => {
    if (!result || !editorRef.current || !monacoRef.current) {
      return;
    }
    const model = editorRef.current.getModel();
    if (!model) {
      return;
    }

    const monaco = monacoRef.current;
    const markers: MonacoEditor.IMarkerData[] = result.issues
      .filter(
        (issue) => issue.line && issue.line > 0 && issue.line <= model.getLineCount()
      )
      .map((issue) => ({
        startLineNumber: issue.line!,
        endLineNumber: issue.line!,
        startColumn: 1,
        endColumn: Math.max(2, model.getLineLength(issue.line!)),
        message: `${issue.severity}: ${issue.message}`,
        severity:
          issue.severity === "Critical" || issue.severity === "High"
            ? monaco.MarkerSeverity.Error
            : issue.severity === "Medium"
              ? monaco.MarkerSeverity.Warning
              : monaco.MarkerSeverity.Info
      }));

    monaco.editor.setModelMarkers(model, "ai-review", markers);
  }, [result]);

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <TopBar
        active="review"
        onRun={run}
        isRunning={loading}
        theme={theme}
        onToggleTheme={onToggleTheme}
        token={token}
        username={username}
        onLogin={onLogin}
        onRegister={onRegister}
        onLogout={onLogout}
      />

      <main className="mx-auto grid max-w-[1600px] grid-cols-1 gap-5 px-6 py-6 xl:grid-cols-[1.25fr_1fr]">
        <section className="rounded-2xl border border-app-border bg-app-panel p-5 shadow-panel">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <FileUploader
                onCodeLoaded={(uploadedFileName, content) => {
                  setFileName(uploadedFileName);
                  setCode(content);
                }}
              />
              <input
                value={fileName ?? ""}
                onChange={(event) => setFileName(event.target.value)}
                placeholder="filename.py"
                className="rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:border-app-accent focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                className="rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text focus:border-app-accent focus:outline-none"
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="typescript">TypeScript</option>
                <option value="java">Java</option>
              </select>
              <span className="text-xs text-app-muted">{lineCount} lines</span>
            </div>
          </div>

          <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <label className="flex items-center gap-2 text-xs text-app-muted">
              <input
                type="checkbox"
                checked={includeProjectContext}
                onChange={(event) => setIncludeProjectContext(event.target.checked)}
              />
              Include repository context in AI review
            </label>
            <span className="text-right text-xs text-app-muted">
              Shortcuts: Ctrl/Cmd+Enter run, Esc clear
            </span>
          </div>

          <textarea
            value={contextText}
            onChange={(event) => setContextText(event.target.value)}
            placeholder="Optional context for AI (intent, constraints, architecture notes)"
            className="mb-3 min-h-20 w-full rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:border-app-accent focus:outline-none"
          />

          <div className="overflow-hidden rounded-2xl border border-app-border">
            <Editor
              height="68vh"
              language={language}
              value={code}
              onChange={(nextValue) => setCode(nextValue ?? "")}
              theme={theme === "dark" ? "vs-dark" : "light"}
              onMount={(editor, monaco) => {
                editorRef.current = editor;
                monacoRef.current = monaco;
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                fontFamily: "IBM Plex Mono",
                scrollBeyondLastLine: false,
                automaticLayout: true
              }}
            />
          </div>
        </section>

        <ReviewPanel
          result={result}
          loading={loading}
          error={error}
          theme={theme}
          onApplyFix={handleApplyFix}
          onIgnoreFix={handleIgnoreFix}
          onAcceptIssue={handleAcceptIssue}
          onIgnoreIssue={handleIgnoreIssue}
          issueDecisions={issueDecisions}
          fixDecisions={fixDecisions}
        />
      </main>
    </div>
  );
}
