import Link from "next/link";
import type { RenderableItem } from "@/lib/types";
import { Kicker } from "./Kicker";

/**
 * Editorial deep brief. Replaces the indigo card with:
 *
 *   ▍ DEEP INSIGHT · CATEGORY
 *   Headline in serif
 *   ── 核心洞見 ─────────────────
 *   body…
 *   ── 底層邏輯 ─────────────────
 *   body…
 *   ── 生態影響 ─────────────────
 *   body…
 *
 * The left rule (2px oxblood) marks the section as "long form" without
 * relying on background tints. Three-part body uses the same serif as
 * instant cards but sits in larger leading for a reading rhythm.
 */
export function DeepInsightCard({ item }: { item: RenderableItem }) {
  const parts = splitThreePart(item.summary);
  const headline = item.title || item.entity || "Untitled";

  return (
    <article className="border-l-2 border-accent pl-6 py-6 space-y-5">
      <header className="space-y-3">
        <Kicker tone="accent">
          Deep Insight
          {item.category && (
            <>
              <span aria-hidden className="mx-2 text-ink-faint">
                ·
              </span>
              <span className="text-ink-soft">{item.category}</span>
            </>
          )}
        </Kicker>
        <h3 className="font-serif text-[26px] leading-snug tracking-[-0.018em] text-ink sm:text-[30px]">
          <Link
            href={`/item/${encodeURIComponent(item.id)}`}
            className="hover:underline"
          >
            {headline}
          </Link>
        </h3>
        <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
          {item.source_name || "source"}
        </p>
      </header>

      <dl className="space-y-5">
        <Section label="核心洞見" body={parts.insight} />
        <Section label="底層邏輯" body={parts.tech_rationale} />
        <Section label="生態影響" body={parts.implication} />
      </dl>

      {item.source_url && (
        <a
          href={item.source_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-accent underline-offset-4 hover:underline"
        >
          Read original
        </a>
      )}
    </article>
  );
}

function Section({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div className="space-y-2">
      <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
        {label}
      </dt>
      <dd className="whitespace-pre-line font-serif text-[17px] leading-[1.65] text-ink">
        {body}
      </dd>
    </div>
  );
}

function splitThreePart(summary: string): {
  insight: string;
  tech_rationale: string;
  implication: string;
} {
  const blocks = (summary || "")
    .split(/\n\s*\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (blocks.length >= 3) {
    return {
      insight: blocks[0]!,
      tech_rationale: blocks[1]!,
      implication: blocks.slice(2).join("\n\n"),
    };
  }
  return { insight: summary, tech_rationale: "", implication: "" };
}
