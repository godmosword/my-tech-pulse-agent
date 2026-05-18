"use client";

import { useEffect, useState } from "react";

/**
 * Three-way theme switch: light, dark, system.
 *
 * Persistence: writes/reads `tech-pulse-theme` in localStorage. layout.tsx
 * ships a tiny inline script that reads the same key before first paint to
 * avoid FOUC; this component owns the post-hydration UI for changing the
 * choice.
 */
type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "tech-pulse-theme";

function readTheme(): Theme {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");
  // Track hydration so the SSR markup matches whatever the inline script set —
  // we only render the actual selection state after mount.
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTheme(readTheme());
    setMounted(true);
  }, []);

  const onPick = (next: Theme) => {
    setTheme(next);
    if (next === "system") {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
    applyTheme(next);
  };

  const options: { value: Theme; label: string; aria: string }[] = [
    { value: "light", label: "日", aria: "白天模式" },
    { value: "dark", label: "夜", aria: "夜晚模式" },
    { value: "system", label: "自動", aria: "跟隨系統設定" },
  ];

  return (
    <div
      role="group"
      aria-label="顯示模式"
      className="inline-flex items-center gap-0 border border-rule font-sans text-kicker font-semibold uppercase tracking-[0.12em]"
    >
      {options.map((opt) => {
        const active = mounted && theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onPick(opt.value)}
            aria-pressed={active}
            aria-label={opt.aria}
            className={`px-2 py-1 transition-colors ${
              active
                ? "bg-ink text-paper"
                : "text-ink-soft hover:text-accent"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
