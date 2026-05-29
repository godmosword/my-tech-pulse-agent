import Link from "next/link";
import {
  bestTimestamp,
  categoryLabel,
  formatRelativeDateline,
  shouldShowConfidenceBadge,
} from "@/lib/digest";
import { publicSummaryLine } from "@/lib/public-excerpt";
import {
  authenticatedPrimaryBody,
  hasGatedLongContent,
} from "@/lib/zh-content";
import {
  PRIORITY_DOT_CLASS,
  PRIORITY_LABEL,
  displayTitle,
  listingZhSubline,
  priorityLevel,
  type RenderableItem,
} from "@/lib/types";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Kicker, MetaDot } from "./Kicker";

interface InstantCardProps {
  item: RenderableItem;
  authenticated: boolean;
  /** Safe path for post-login redirect (e.g. `/item/abc`). */
  returnToPath: string;
  /** list = homepage/theme rows; full = item detail depth. */
  variant?: "list" | "full";
}

/**
 * Editorial article entry. Drops the card box and replaces it with a vertical
 * rhythm:
 *
 *   KICKER (category · source · date)
 *   Headline in serif
 *   繁中導讀 +（登入後）完整中譯正文  — full variant only
 *
 * The hairline between entries is owned by ThemeSection, not this component,
 * so groups of items share one rhythm without doubled rules.
 */
export function InstantCard({
  item,
  authenticated,
  returnToPath,
  variant = "full",
}: InstantCardProps) {
  const headline = displayTitle(item);
  const meta = formatRelativeDateline(bestTimestamp(item));
  const cat = categoryLabel(item.category);
  const loginHref = `/login?returnTo=${encodeURIComponent(returnToPath)}`;
  const previewLine = publicSummaryLine(item);
  const isList = variant === "list";
  const subline = isList
    ? listingZhSubline(item) ?? (authenticated ? null : previewLine)
    : null;

  return (
    <article className={isList ? "space-y-2 py-4" : "space-y-3 py-6"}>
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

      <h3 className="font-serif text-editorial-headline text-ink">
        <Link href={`/item/${encodeURIComponent(item.id)}`} className="hover:underline">
          {headline}
        </Link>
      </h3>

      {isList ? (
        subline && (
          <p className="font-sans text-editorial-body leading-snug text-ink-soft line-clamp-2">
            {subline}
          </p>
        )
      ) : authenticated ? (
        <>
          {item.zh_summary && (
            <p className="font-sans text-dek text-ink">{item.zh_summary}</p>
          )}
          {authenticatedPrimaryBody(item) && (
            <p className="whitespace-pre-line font-serif text-editorial-body text-ink">
              {authenticatedPrimaryBody(item)}
            </p>
          )}
          {item.zh_body?.trim() && item.summary?.trim() && (
            <details className="font-sans text-meta text-ink-soft">
              <summary className="cursor-pointer text-accent underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
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

      <CardFooter item={item} authenticated={authenticated} compact={isList} />
    </article>
  );
}

function CardFooter({
  item,
  authenticated,
  compact,
}: {
  item: RenderableItem;
  authenticated: boolean;
  compact: boolean;
}) {
  const level = priorityLevel(item.score);
  const showScore = item.score_status !== "fallback" && item.score > 0;
  const tickers = item.tickers ?? [];
  const wh = item.what_happened?.trim() ?? "";
  const why = item.why_it_matters?.trim() ?? "";
  const canExpand = !compact && authenticated && (Boolean(wh) || Boolean(why));
  const showConfidence = shouldShowConfidenceBadge(item);

  return (
    <div className="space-y-2 pt-1">
      {(showScore || showConfidence || tickers.length > 0 || (!compact && item.source_url)) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
          {showScore && (
            <span className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className={`inline-block h-2 w-2 rounded-full ${PRIORITY_DOT_CLASS[level]}`}
              />
              <span className="font-mono normal-case tracking-normal text-ink">
                {item.score.toFixed(1)}
              </span>
              <span className="text-ink-faint">/ 10</span>
              {!compact && <span className="text-ink">{PRIORITY_LABEL[level]}</span>}
            </span>
          )}
          {showConfidence && <ConfidenceBadge item={item} />}
          {tickers.length > 0 && (
            <span
              aria-label={`相關代號：${tickers.join(", ")}`}
              className="flex flex-wrap items-center gap-1.5 normal-case tracking-normal"
            >
              <span className="text-ink-faint">代號</span>
              {tickers.map((t) => (
                <span
                  key={t}
                  className="rounded-sm border border-rule px-1.5 py-0.5 font-mono text-kicker text-ink"
                >
                  {t}
                </span>
              ))}
            </span>
          )}
          {!compact && item.source_url && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              className="underline-offset-4 hover:text-accent hover:underline"
            >
              阅读原文
            </a>
          )}
        </div>
      )}

      {canExpand && (
        <details className="font-sans text-meta text-ink-soft">
          <summary className="cursor-pointer text-kicker font-semibold uppercase tracking-[0.12em] text-accent underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
            展開分析
          </summary>
          <div className="mt-3 space-y-3 text-body text-ink">
            {wh && (
              <div>
                <p className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-faint">
                  事實
                </p>
                <p className="mt-1 whitespace-pre-line">{wh}</p>
              </div>
            )}
            {why && (
              <div>
                <p className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-faint">
                  含義
                </p>
                <p className="mt-1 whitespace-pre-line">{why}</p>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
