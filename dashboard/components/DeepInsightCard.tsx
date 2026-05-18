import Link from "next/link";
import type { RenderableItem } from "@/lib/types";
import { publicSummaryLine } from "@/lib/public-excerpt";
import {
  authenticatedPrimaryBody,
  hasGatedLongContent,
} from "@/lib/zh-content";
import { Kicker } from "./Kicker";

interface DeepInsightCardProps {
  item: RenderableItem;
  authenticated: boolean;
  returnToPath: string;
}

/**
 * Editorial deep brief. Replaces the indigo card with:
 *
 *   ▍ DEEP INSIGHT · CATEGORY
 *   Headline in serif
 *   繁中導讀 +（登入後）完整洞見正文
 */
export function DeepInsightCard({
  item,
  authenticated,
  returnToPath,
}: DeepInsightCardProps) {
  const parts = splitThreePart(item.summary);
  const headline = item.title || item.entity || "Untitled";
  const loginHref = `/login?returnTo=${encodeURIComponent(returnToPath)}`;
  const teaser = publicSummaryLine(item);
  const bodyZh = authenticatedPrimaryBody(item);
  const useFlatZhBody = Boolean(item.zh_body?.trim());

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

      {authenticated ? (
        useFlatZhBody ? (
          <div className="space-y-4">
            {item.zh_summary?.trim() && (
              <p className="font-sans text-dek text-ink">{item.zh_summary}</p>
            )}
            {bodyZh && (
              <p className="whitespace-pre-line font-serif text-[17px] leading-[1.65] text-ink">
                {bodyZh}
              </p>
            )}
          </div>
        ) : (
          <dl className="space-y-5">
            <Section label="核心洞見" body={parts.insight} />
            <Section label="底層邏輯" body={parts.tech_rationale} />
            <Section label="生態影響" body={parts.implication} />
          </dl>
        )
      ) : (
        <div className="space-y-3">
          {teaser && (
            <p className="whitespace-pre-line font-serif text-[17px] leading-[1.65] text-ink">
              {teaser}
            </p>
          )}
          {hasGatedLongContent(item) && (
            <p className="font-sans text-meta text-ink-soft">
              <Link href={loginHref} className="text-accent underline-offset-4 hover:underline">
                登入以閱讀完整洞見
              </Link>
            </p>
          )}
        </div>
      )}

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
