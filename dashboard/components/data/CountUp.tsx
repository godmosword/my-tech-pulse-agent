"use client";

import { useEffect, useRef, useState } from "react";

interface CountUpProps {
  /** Final numeric value to animate to. */
  value: number;
  /** Formats the interpolated number for display (default: String). */
  format?: (n: number) => string;
  /** Animation duration in ms. */
  durationMs?: number;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Counts a number up to its final value on mount. SSR and the no-JS / reduced-
 * motion paths render the final value immediately, so the displayed text always
 * settles on exactly `value` — only the journey there is animated.
 */
export function CountUp({ value, format = String, durationMs = 700 }: CountUpProps) {
  const [display, setDisplay] = useState(value);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(value) || prefersReducedMotion()) {
      setDisplay(value);
      return;
    }

    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // easeOutCubic — fast then settle.
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (value - from) * eased);
      if (t < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        setDisplay(value);
      }
    };
    frame.current = requestAnimationFrame(tick);

    return () => {
      if (frame.current != null) cancelAnimationFrame(frame.current);
    };
  }, [value, durationMs]);

  return <>{format(display)}</>;
}
