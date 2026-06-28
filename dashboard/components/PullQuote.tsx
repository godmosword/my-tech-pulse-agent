import type { ReactNode } from "react";

interface PullQuoteProps {
  children: ReactNode;
  /** Optional attribution shown beneath the quote (source, ticker, etc.). */
  cite?: string;
}

/**
 * Editorial pull quote. Reuses the sanctioned accent left-rail (see DESIGN.md
 * "Allowed accents") with an enlarged serif face — a reading anchor for
 * long-form deep briefs, not a generic card.
 */
export function PullQuote({ children, cite }: PullQuoteProps) {
  return (
    <figure className="my-6 max-w-column border-l-2 border-accent pl-5">
      <blockquote className="text-justify-cjk font-serif text-editorial-headline leading-snug text-ink">
        {children}
      </blockquote>
      {cite && (
        <figcaption className="mt-2 font-sans text-kicker uppercase tracking-[0.12em] text-ink-faint">
          {cite}
        </figcaption>
      )}
    </figure>
  );
}
