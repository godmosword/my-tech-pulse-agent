import Link from "next/link";
import { displayTitle, type RenderableItem } from "@/lib/types";
import { publicSummaryLine } from "@/lib/public-excerpt";
import {
  authenticatedPrimaryBody,
  hasGatedLongContent,
} from "@/lib/zh-content";
import { LoginToReadCta } from "./LoginToReadCta";
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
  const headline = displayTitle(item);
  const teaser = publicSummaryLine(item);
  const bodyZh = authenticatedPrimaryBody(item);
  const useFlatZhBody = Boolean(item.zh_body?.trim());

  return (
    <article className="border-l-2 border-accent pl-6 py-6 space-y-5 border-b border-rule">
      <header className="max-w-column space-y-3">
        <Kicker tone="accent">
          <span className="leading-[1.1]">深度洞見</span>
          {item.category && (
            <>
              <span aria-hidden className="mx-2 text-ink-faint">
                ·
              </span>
              <span className="text-ink-soft leading-[1.1]">{item.category}</span>
            </>
          )}
        </Kicker>
        <h3 className="font-serif text-editorial-headline text-ink">
          <Link
            href={`/item/${encodeURIComponent(item.id)}`}
            className="bg-[linear-gradient(to_right,var(--color-accent),var(--color-accent))] bg-[length:0%_1px] bg-left-bottom bg-no-repeat transition-[background-size,color] duration-300 ease-out hover:bg-[length:100%_1px] hover:text-accent"
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
          <div className="max-w-column space-y-4">
            {item.zh_summary?.trim() && (
              <p className="font-sans text-dek text-ink">{item.zh_summary}</p>
            )}
            {bodyZh && (
              <p className="text-justify-cjk whitespace-pre-line font-serif text-dek leading-[1.65] text-ink">
                {bodyZh}
              </p>
            )}
          </div>
        ) : (
          <dl className="max-w-column">
            <Section label="核心洞見" body={parts.insight} />
            {parts.tech_rationale && <Fleuron />}
            <Section label="底層邏輯" body={parts.tech_rationale} />
            {parts.implication && <Fleuron />}
            <Section label="生態影響" body={parts.implication} />
          </dl>
        )
      ) : (
        <div className="max-w-column space-y-3">
          {teaser && (
            <div className="relative">
              <p className="text-justify-cjk whitespace-pre-line font-serif text-dek leading-[1.65] text-ink">
                {teaser}
              </p>
              {hasGatedLongContent(item) && (
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-paper to-transparent"
                />
              )}
            </div>
          )}
          {hasGatedLongContent(item) && (
            <LoginToReadCta returnToPath={returnToPath} />
          )}
        </div>
      )}

      <div className="flex items-center gap-4">
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-accent underline-offset-4 hover:underline"
          >
            閱讀原文
          </a>
        )}
        <span
          aria-hidden
          className="ml-auto font-serif text-base leading-none text-ink-faint"
          title="end of article"
        >
          ※
        </span>
      </div>
    </article>
  );
}

function Fleuron() {
  return (
    <div
      aria-hidden
      className="my-5 flex items-center justify-center gap-3 text-ink-faint"
    >
      <span className="h-px w-10 bg-rule" />
      <span className="font-serif text-sm leading-none">❦</span>
      <span className="h-px w-10 bg-rule" />
    </div>
  );
}

function Section({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div className="space-y-2">
      <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
        {label}
      </dt>
      <dd className="text-justify-cjk whitespace-pre-line font-serif text-dek leading-[1.65] text-ink">
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
