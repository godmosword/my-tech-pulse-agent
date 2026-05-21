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
        // next/font assigns these vars on <body>; see app/layout.tsx
        sans: [
          "var(--font-sans)",
          "var(--font-sans-cjk)",
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang TC",
          "Microsoft JhengHei",
          "sans-serif",
        ],
        serif: [
          "var(--font-serif)",
          "var(--font-serif-cjk)",
          "ui-serif",
          "Georgia",
          "Cambria",
          "Times New Roman",
          "Songti TC",
          "serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      // Semantic tokens — CSS vars defined in app/globals.css flip with
      // prefers-color-scheme so no per-component `dark:` overrides needed.
      colors: {
        paper: {
          DEFAULT: "var(--color-paper)",
          tint: "var(--color-paper-tint)",
        },
        ink: {
          DEFAULT: "var(--color-ink)",
          soft: "var(--color-ink-soft)",
          faint: "var(--color-ink-faint)",
        },
        rule: "var(--color-rule)",
        accent: "var(--color-accent)",
      },
      fontSize: {
        // UI chrome (nav, labels, meta) — sized closer to article dek/body (17–18px).
        kicker: ["13px", { lineHeight: "1.25", letterSpacing: "0.1em" }],
        meta: ["14px", { lineHeight: "1.5" }],
        body: ["16px", { lineHeight: "1.65" }],
        dek: ["17px", { lineHeight: "1.55" }],
        headline: ["28px", { lineHeight: "1.18", letterSpacing: "-0.018em" }],
        hero: ["40px", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
      },
      maxWidth: {
        column: "640px", // long-read text column
      },
    },
  },
  plugins: [],
};

export default config;
