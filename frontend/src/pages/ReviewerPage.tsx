import Editor from "@monaco-editor/react";
import { useMemo, useState } from "react";

import { runReview } from "../api/client";
import { FileUploader } from "../components/FileUploader";
import { ReviewPanel } from "../components/ReviewPanel";
import { TopBar } from "../components/TopBar";
import type { ReviewResponse } from "../types/review";

interface ReviewerPageProps {
  token: string | null;
  username: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
  onReviewCompleted: () => void;
}

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
  onLogin,
  onRegister,
  onLogout,
  onReviewCompleted
}: ReviewerPageProps): JSX.Element {
  const [code, setCode] = useState(DEFAULT_SAMPLE);
  const [language, setLanguage] = useState("python");
  const [fileName, setFileName] = useState<string | undefined>("sample.py");
  const [result, setResult] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lineCount = useMemo(() => code.split(/\r?\n/).length, [code]);

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
          language
        },
        token
      );
      setResult(response);
      onReviewCompleted();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Review failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <TopBar
        active="review"
        onRun={run}
        isRunning={loading}
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

          <div className="overflow-hidden rounded-2xl border border-app-border">
            <Editor
              height="72vh"
              language={language}
              value={code}
              onChange={(nextValue) => setCode(nextValue ?? "")}
              theme="vs-dark"
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

        <ReviewPanel result={result} loading={loading} error={error} />
      </main>
    </div>
  );
}
