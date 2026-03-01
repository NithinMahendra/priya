import { NavLink } from "react-router-dom";
import { useState } from "react";

interface TopBarProps {
  active: "review" | "dashboard";
  onRun?: () => Promise<void>;
  isRunning?: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  token: string | null;
  username: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onLogout: () => void;
}

export function TopBar({
  active,
  onRun,
  isRunning = false,
  theme,
  onToggleTheme,
  token,
  username,
  onLogin,
  onRegister,
  onLogout
}: TopBarProps): JSX.Element {
  const [inputUsername, setInputUsername] = useState("");
  const [inputPassword, setInputPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [authError, setAuthError] = useState("");

  const submitAuth = async (mode: "login" | "register") => {
    if (!inputUsername || !inputPassword) {
      setAuthError("Enter username and password.");
      return;
    }
    setBusy(true);
    setAuthError("");
    try {
      if (mode === "login") {
        await onLogin(inputUsername, inputPassword);
      } else {
        await onRegister(inputUsername, inputPassword);
      }
      setInputPassword("");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  };

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-xl px-3 py-2 text-sm transition ${
      isActive
        ? "bg-app-accent/20 text-app-accent"
        : "text-app-muted hover:bg-app-panelSoft hover:text-app-text"
    }`;

  return (
    <header className="sticky top-0 z-20 border-b border-app-border bg-app-bg/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-6">
          <div>
            <h1 className="text-lg font-semibold text-app-text">AI Code Reviewer</h1>
            <p className="text-xs text-app-muted">Static + Security + LLM semantic checks</p>
          </div>
          <nav className="flex items-center gap-2">
            <NavLink to="/" className={navClass} end>
              Reviewer
            </NavLink>
            <NavLink to="/dashboard" className={navClass}>
              Dashboard
            </NavLink>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded-xl border border-app-border px-3 py-2 text-xs text-app-muted transition hover:border-app-accent hover:text-app-text"
          >
            {theme === "dark" ? "Light" : "Dark"} Mode
          </button>

          {active === "review" && onRun && (
            <button
              type="button"
              onClick={() => void onRun()}
              disabled={isRunning}
              className="rounded-xl bg-app-accent px-4 py-2 text-sm font-semibold text-slate-900 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-65"
            >
              {isRunning ? "Reviewing..." : "Run Review"}
            </button>
          )}

          {token ? (
            <div className="flex items-center gap-3 rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm">
              <span className="text-app-text">{username}</span>
              <button
                type="button"
                onClick={onLogout}
                className="text-app-muted transition hover:text-app-text"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <input
                value={inputUsername}
                onChange={(event) => setInputUsername(event.target.value)}
                placeholder="username"
                className="w-32 rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:border-app-accent focus:outline-none"
              />
              <input
                type="password"
                value={inputPassword}
                onChange={(event) => setInputPassword(event.target.value)}
                placeholder="password"
                className="w-32 rounded-xl border border-app-border bg-app-panelSoft px-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:border-app-accent focus:outline-none"
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void submitAuth("login")}
                className="rounded-xl border border-app-border px-3 py-2 text-xs text-app-text transition hover:border-app-accent disabled:opacity-60"
              >
                Login
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void submitAuth("register")}
                className="rounded-xl border border-app-border px-3 py-2 text-xs text-app-text transition hover:border-app-accent disabled:opacity-60"
              >
                Register
              </button>
              {authError && <span className="max-w-52 text-xs text-red-300">{authError}</span>}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
