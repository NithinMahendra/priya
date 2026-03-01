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
          bg: "#0b1014",
          panel: "#111821",
          panelSoft: "#16222e",
          border: "#233243",
          text: "#d2e5f2",
          muted: "#7e97ab",
          accent: "#2ac7b6"
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
