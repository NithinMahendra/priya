import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem"
      },
      colors: {
        app: {
          bg: "rgb(var(--app-bg) / <alpha-value>)",
          panel: "rgb(var(--app-panel) / <alpha-value>)",
          panelSoft: "rgb(var(--app-panel-soft) / <alpha-value>)",
          border: "rgb(var(--app-border) / <alpha-value>)",
          text: "rgb(var(--app-text) / <alpha-value>)",
          muted: "rgb(var(--app-muted) / <alpha-value>)",
          accent: "rgb(var(--app-accent) / <alpha-value>)"
        }
      },
      boxShadow: {
        panel: "0 12px 30px rgba(0, 0, 0, 0.35)",
        glow: "0 0 0 1px rgba(42, 199, 182, 0.2), 0 10px 30px rgba(42, 199, 182, 0.12)"
      },
      fontFamily: {
        sans: ["Space Grotesk", "ui-sans-serif", "system-ui"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular"]
      }
    }
  },
  plugins: []
};

export default config;
