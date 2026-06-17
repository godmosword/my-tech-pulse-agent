import Link from "next/link";

import type { MaterialMoveView } from "@/lib/material-move";

/**
 * One decision row, shared by the authoritative brief and the live fallback.
 * Keeps the first glance light: affected tickers + headline + posture on the
 * main line, the reason on the next, and the supporting detail (market state,
 * falsification, next check) tucked into a native <details> so it is there when
 * wanted but not crowding the scan. <details> is keyboard-operable as-is.
 */
export function MaterialMoveRow({ view }: { view: MaterialMoveView }) {
  const hasDetail =
    view.marketFlags.length > 0 || Boolean(view.falsification) || Boolean(view.nextCheck);

  return (
    <li className="border-b border-rule py-2 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          {view.affectedTickers.length > 0 && (
            <span className="mr-2 inline-flex flex-wrap gap-1 align-middle">
              {view.affectedTickers.map((ticker) => (
                <span
                  key={ticker}
                  className="rounded border border-rule px-1.5 py-0.5 font-mono text-meta text-ink-soft"
                >
                  {ticker}
                </span>
              ))}
            </span>
          )}
          {view.href ? (
            <Link
              href={view.href}
              className="font-sans text-body text-ink hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {view.title}
            </Link>
          ) : (
            <span className="font-sans text-body text-ink">{view.title}</span>
          )}
        </div>
        <span className={`shrink-0 font-sans text-meta font-semibold ${view.postureClass}`}>
          {view.postureLabel}
        </span>
      </div>

      {view.reason && (
        <p className="mt-1 font-sans text-meta text-ink-soft">{view.reason}</p>
      )}

      {hasDetail && (
        <details className="mt-1">
          <summary className="cursor-pointer font-sans text-meta text-ink-faint hover:text-accent">
            細節
          </summary>
          <div className="mt-1 space-y-0.5 font-sans text-meta text-ink-faint">
            {view.marketFlags.length > 0 && (
              <p>市場狀態：{view.marketFlags.join("、")}</p>
            )}
            {view.falsification && <p>反證：{view.falsification}</p>}
            {view.nextCheck && <p>下次檢查：{view.nextCheck}</p>}
          </div>
        </details>
      )}
    </li>
  );
}
