import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useMemo, useState } from "react";

import { login, register } from "./api/client";
import { DashboardPage } from "./pages/DashboardPage";
import { ReviewerPage } from "./pages/ReviewerPage";

function parseJwtSubject(token: string): string | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) {
      return null;
    }
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const decoded = JSON.parse(atob(padded));
    return (decoded.sub as string) ?? null;
  } catch {
    return null;
  }
}

export default function App(): JSX.Element {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));
  const [dashboardRefresh, setDashboardRefresh] = useState(0);
  const username = useMemo(() => (token ? parseJwtSubject(token) : null), [token]);

  const handleLogin = async (inputUsername: string, password: string) => {
    const accessToken = await login(inputUsername, password);
    localStorage.setItem("token", accessToken);
    setToken(accessToken);
  };

  const handleRegister = async (inputUsername: string, password: string) => {
    await register(inputUsername, password);
    const accessToken = await login(inputUsername, password);
    localStorage.setItem("token", accessToken);
    setToken(accessToken);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setToken(null);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <ReviewerPage
              token={token}
              username={username}
              onLogin={handleLogin}
              onRegister={handleRegister}
              onLogout={handleLogout}
              onReviewCompleted={() => setDashboardRefresh((prev) => prev + 1)}
            />
          }
        />
        <Route
          path="/dashboard"
          element={
            <DashboardPage
              token={token}
              username={username}
              refreshSignal={dashboardRefresh}
              onLogin={handleLogin}
              onRegister={handleRegister}
              onLogout={handleLogout}
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
