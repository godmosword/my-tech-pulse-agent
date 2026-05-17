import type { ReactNode } from "react";

interface KickerProps {
  children: ReactNode;
  className?: string;
  /**
   * "accent" renders in oxblood — reserve for editorial emphasis (e.g. the
   * DEEP INSIGHT label). Default "soft" stays neutral muted ink.
   */
  tone?: "soft" | "accent";
  as?: "div" | "p" | "span";
}

/**
 * Editorial kicker label: uppercase small-caps eyebrow shown above headlines
 * or between meta items. Spans accept inline meta strings separated by
 * `<MetaDot/>`; div/p variants are for standalone eyebrows.
 */
export function Kicker({
  children,
  className,
  tone = "soft",
  as: Tag = "div",
}: KickerProps) {
  const toneClass = tone === "accent" ? "text-accent" : "text-ink-soft";
  return (
    <Tag
      className={`font-sans text-kicker font-semibold uppercase tracking-[0.12em] ${toneClass} ${className ?? ""}`}
    >
      {children}
    </Tag>
  );
}

/** Inline `·` separator with editorial spacing for kicker meta strings. */
export function MetaDot() {
  return (
    <span aria-hidden className="mx-2 text-ink-faint">
      ·
    </span>
  );
}
