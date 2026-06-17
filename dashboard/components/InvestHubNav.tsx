"use client";

import { useEffect, useState } from "react";

export interface HubSection {
  id: string;
  label: string;
}

/**
 * Sticky in-page anchor nav for the Invest hub's deep-analysis sections.
 *
 * Deliberately uses plain `#anchor` links (not mutually-exclusive tabs): every
 * section stays in the DOM, so browser find, deep links, and back/forward keep
 * working. JS only layers an active-section highlight via IntersectionObserver;
 * with JS disabled the anchors still scroll. This is a presentation-only client
 * shell — it holds no data and fetches nothing.
 */
export function InvestHubNav({ sections }: { sections: HubSection[] }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const targets = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    if (targets.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]?.target.id) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 },
    );

    targets.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav
      aria-label="投資深入分析導覽"
      className="section-band sticky top-2 z-10 -mx-1 mb-2 flex flex-wrap gap-x-4 gap-y-1 px-3 py-2"
    >
      {sections.map((s) => {
        const isActive = active === s.id;
        return (
          <a
            key={s.id}
            href={`#${s.id}`}
            aria-current={isActive ? "true" : undefined}
            className={`font-sans text-meta font-semibold uppercase tracking-[0.08em] hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              isActive ? "text-accent" : "text-ink-faint"
            }`}
          >
            {s.label}
          </a>
        );
      })}
    </nav>
  );
}
