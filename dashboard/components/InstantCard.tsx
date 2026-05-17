import Link from "next/link";
import {
  categoryLabel,
  formatMetaDate,
  formatScore,
} from "@/lib/digest";
import type { RenderableItem } from "@/lib/types";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Kicker, MetaDot } from "./Kicker";

/**
 * Editorial article entry. Drops the card box and replaces it with a vertical
 * rhythm:
 *
 *   KICKER (category · source · date)
 *   Headline in serif
 *   💡 Chinese dek — the hero translation
 *   English summary in muted body
 *   confidence small caps                              7.6 / 10
 *
 * The hairline between entries is owned by ThemeSection, not this component,
 * so groups of items share one rhythm without doubled rules.
 */
export function InstantCard({ item }: { item: RenderableItem }) {
  const headline = item.title || item.entity || "Untitled";
  const meta = formatMetaDate(item.published_at_iso || item.delivered_at_iso);
  const cat = categoryLabel(item.category);

  return (
    <article className="space-y-3 py-6">
      <Kicker as="div" className="flex flex-wrap items-center">
        <span>{cat}</span>
        {item.source_name && (
          <>
            <MetaDot />
            <span>{item.source_name}</span>
          </>
        )}
        {meta && (
          <>
            <MetaDot />
            <span>{meta}</span>
          </>
        )}
      </Kicker>

      <h3 className="font-serif text-[22px] leading-snug tracking-[-0.018em] text-ink sm:text-[26px]">
        <Link href={`/item/${encodeURIComponent(item.id)}`} className="hover:underline">
          {headline}
        </Link>
      </h3>

      {item.zh_summary && (
        <p className="font-sans text-dek text-ink">{item.zh_summary}</p>
      )}

      {item.summary && (
        <p className="whitespace-pre-line font-sans text-body text-ink-soft">
          {item.summary}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 pt-1">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <ConfidenceBadge item={item} />
          {item.source_url && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft underline-offset-4 hover:text-accent hover:underline"
            >
              Read original
            </a>
          )}
        </div>
        <span className="font-mono text-meta tabular-nums text-ink-soft">
          {item.score > 0 ? `${formatScore(item.score)} / 10` : "—"}
        </span>
      </div>
    </article>
  );
}
