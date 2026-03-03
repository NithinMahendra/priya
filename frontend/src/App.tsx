import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { getCurrentUser, login, register } from "./api/client";
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
  const [validatedUsername, setValidatedUsername] = useState<string | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">(
    () => (localStorage.getItem("theme") as "dark" | "light") ?? "dark"
  );
  const [dashboardRefresh, setDashboardRefresh] = useState(0);
  const username = useMemo(
    () => validatedUsername ?? (token ? parseJwtSubject(token) : null),
    [token, validatedUsername]
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!token) {
      setValidatedUsername(null);
      return;
    }
    let active = true;
    const validateToken = async () => {
      try {
        const user = await getCurrentUser(token);
        if (!active) {
          return;
        }
        setValidatedUsername(user.username);
      } catch {
        if (!active) {
          return;
        }
        localStorage.removeItem("token");
        setToken(null);
        setValidatedUsername(null);
      }
    };
    void validateToken();
    const intervalId = window.setInterval(() => {
      void validateToken();
    }, 60000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [token]);

  const handleLogin = async (inputUsername: string, password: string) => {
    const accessToken = await login(inputUsername, password);
    localStorage.setItem("token", accessToken);
    setToken(accessToken);
    setValidatedUsername(inputUsername);
  };

  const handleRegister = async (inputUsername: string, password: string) => {
    await register(inputUsername, password);
    const accessToken = await login(inputUsername, password);
    localStorage.setItem("token", accessToken);
    setToken(accessToken);
    setValidatedUsername(inputUsername);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setValidatedUsername(null);
  };

  const toggleTheme = () => setTheme((prev) => (prev === "dark" ? "light" : "dark"));

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <ReviewerPage
              token={token}
              username={username}
              theme={theme}
              onToggleTheme={toggleTheme}
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
              theme={theme}
              onToggleTheme={toggleTheme}
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
