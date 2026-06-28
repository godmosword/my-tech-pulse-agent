"use client";

import type { ReactNode } from "react";

import { useReveal } from "@/lib/use-reveal";

interface RevealProps {
  children: ReactNode;
  /** Stagger delay in ms (e.g. index * 60) for sequential entrances. */
  delayMs?: number;
  className?: string;
}

/**
 * Client wrapper that fades + lifts its children into view on scroll. Children
 * stay server-rendered (passed as props). Degrades to fully visible without JS
 * and collapses to no motion under prefers-reduced-motion. See lib/use-reveal.
 */
export function Reveal({ children, delayMs = 0, className }: RevealProps) {
  const ref = useReveal<HTMLDivElement>({ delayMs });
  return (
    <div ref={ref} className={`reveal${className ? ` ${className}` : ""}`}>
      {children}
    </div>
  );
}
