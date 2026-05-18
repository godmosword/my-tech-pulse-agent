import Link from "next/link";
import {
  categoryLabel,
  formatMetaDate,
} from "@/lib/digest";
import { publicSummaryLine } from "@/lib/public-excerpt";
import {
  authenticatedPrimaryBody,
  hasGatedLongContent,
} from "@/lib/zh-content";
import type { RenderableItem } from "@/lib/types";
import { Kicker, MetaDot } from "./Kicker";

interface InstantCardProps {
  item: RenderableItem;
  authenticated: boolean;
  /** Safe path for post-login redirect (e.g. `/item/abc`). */
  returnToPath: string;
}

/**
 * Editorial article entry. Drops the card box and replaces it with a vertical
 * rhythm:
 *
 *   KICKER (category · source · date)
 *   Headline in serif
 *   繁中導讀 +（登入後）完整中譯正文
 *
 * The hairline between entries is owned by ThemeSection, not this component,
 * so groups of items share one rhythm without doubled rules.
 */
export function InstantCard({ item, authenticated, returnToPath }: InstantCardProps) {
  const headline = item.title || item.entity || "Untitled";
  const meta = formatMetaDate(item.published_at_iso || item.delivered_at_iso);
  const cat = categoryLabel(item.category);
  const loginHref = `/login?returnTo=${encodeURIComponent(returnToPath)}`;
  const previewLine = publicSummaryLine(item);

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

      {authenticated ? (
        <>
          {item.zh_summary && (
            <p className="font-sans text-dek text-ink">{item.zh_summary}</p>
          )}
          {authenticatedPrimaryBody(item) && (
            <p className="whitespace-pre-line font-serif text-[17px] leading-[1.65] text-ink">
              {authenticatedPrimaryBody(item)}
            </p>
          )}
          {item.zh_body?.trim() && item.summary?.trim() && (
            <details className="font-sans text-meta text-ink-soft">
              <summary className="cursor-pointer text-accent underline-offset-4 hover:underline">
                英文原文摘要
              </summary>
              <p className="mt-2 whitespace-pre-line text-body text-ink-soft">
                {item.summary}
              </p>
            </details>
          )}
        </>
      ) : (
        <>
          {previewLine && (
            <p className="font-sans text-dek text-ink">{previewLine}</p>
          )}
          {hasGatedLongContent(item) && (
            <p className="font-sans text-meta text-ink-soft">
              <Link href={loginHref} className="text-accent underline-offset-4 hover:underline">
                登入以閱讀完整中文全文
              </Link>
            </p>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 pt-1">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
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
      </div>
    </article>
  );
}
