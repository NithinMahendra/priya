import { useEffect, useMemo, useState } from "react";
import { Pie, PieChart, Cell, ResponsiveContainer, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts";

import { getDashboardMetrics } from "../api/client";
import { TopBar } from "../components/TopBar";
import type { DashboardMetrics } from "../types/review";

interface DashboardPageProps {
  token: string | null;
  username: string | null;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  refreshSignal: number;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
}

const pieColors = ["#ef4444", "#fb923c", "#facc15", "#22c55e"];

export function DashboardPage({
  token,
  username,
  theme,
  onToggleTheme,
  refreshSignal,
  onLogin,
  onRegister,
  onLogout
}: DashboardPageProps): JSX.Element {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setMetrics(null);
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getDashboardMetrics(token);
        setMetrics(data);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load dashboard.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [token, refreshSignal]);

  const pieData = useMemo(() => {
    if (!metrics) {
      return [];
    }
    return [
      { name: "Critical", value: metrics.issue_distribution.Critical ?? 0 },
      { name: "High", value: metrics.issue_distribution.High ?? 0 },
      { name: "Medium", value: metrics.issue_distribution.Medium ?? 0 },
      { name: "Low", value: metrics.issue_distribution.Low ?? 0 }
    ];
  }, [metrics]);

  const trendData = useMemo(() => {
    if (!metrics) {
      return [];
    }
    return metrics.score_trend.map((point) => ({
      score: point.score,
      date: new Date(point.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })
    }));
  }, [metrics]);

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <TopBar
        active="dashboard"
        theme={theme}
        onToggleTheme={onToggleTheme}
        token={token}
        username={username}
        onLogin={onLogin}
        onRegister={onRegister}
        onLogout={onLogout}
      />

      <main className="mx-auto max-w-[1600px] space-y-5 px-6 py-6">
        {!token && (
          <section className="rounded-2xl border border-app-border bg-app-panel p-5 text-sm text-app-muted shadow-panel">
            Login to view issue distribution and score trend analytics.
          </section>
        )}

        {error && (
          <section className="rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </section>
        )}

        {loading && (
          <section className="rounded-2xl border border-app-border bg-app-panel p-4 text-sm text-app-muted shadow-panel">
            Loading dashboard metrics...
          </section>
        )}

        {metrics && !loading && (
          <>
            <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Submissions" value={String(metrics.submissions)} />
              <MetricCard label="Average Score" value={String(metrics.average_score)} />
              <MetricCard
                label="Latest Score"
                value={String(metrics.score_trend[metrics.score_trend.length - 1]?.score ?? 0)}
              />
              <MetricCard label="Critical Issues" value={String(metrics.issue_distribution.Critical ?? 0)} />
            </section>

            <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <article className="rounded-2xl border border-app-border bg-app-panel p-5 shadow-panel">
                <h2 className="mb-3 text-sm font-semibold text-app-text">Issue Distribution</h2>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={110} innerRadius={58}>
                        {pieData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "#16222e",
                          border: "1px solid #233243",
                          borderRadius: "12px",
                          color: "#d2e5f2"
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </article>

              <article className="rounded-2xl border border-app-border bg-app-panel p-5 shadow-panel">
                <h2 className="mb-3 text-sm font-semibold text-app-text">Score Trend</h2>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData}>
                      <CartesianGrid stroke="#233243" strokeDasharray="4 4" />
                      <XAxis dataKey="date" stroke="#7e97ab" />
                      <YAxis stroke="#7e97ab" domain={[0, 100]} />
                      <Tooltip
                        contentStyle={{
                          background: "#16222e",
                          border: "1px solid #233243",
                          borderRadius: "12px",
                          color: "#d2e5f2"
                        }}
                      />
                      <Line type="monotone" dataKey="score" stroke="#2ac7b6" strokeWidth={3} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </article>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: string;
}

function MetricCard({ label, value }: MetricCardProps): JSX.Element {
  return (
    <article className="rounded-2xl border border-app-border bg-app-panel p-4 shadow-panel">
      <p className="text-xs uppercase tracking-wide text-app-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-app-text">{value}</p>
    </article>
  );
}
