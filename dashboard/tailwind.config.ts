import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang TC",
          "Noto Sans TC",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      // Semantic tokens map to CSS variables so the whole palette can flip
      // under prefers-color-scheme without per-component `dark:` overrides.
      // Concrete values live in app/globals.css.
      colors: {
        ink: {
          DEFAULT: "var(--color-ink)",
          muted: "var(--color-ink-muted)",
          subtle: "var(--color-ink-subtle)",
        },
        surface: {
          DEFAULT: "var(--color-surface)",
          alt: "var(--color-surface-alt)",
          deep: "var(--color-surface-deep)",
        },
      },
    },
  },
  plugins: [],
};

export default config;
