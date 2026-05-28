import type { Metadata } from "next";
import Link from "next/link";

import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
import { listEarningsSince } from "@/lib/earnings-firestore";
import { classifyTier, type PortfolioTier } from "@/lib/portfolio-metrics";
import { getPortfolioTierSets } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "投資訊號排行",
  description: "依綜合投資訊號分數排序的近期財報。",
};

const FACTOR_LABELS: Record<string, string> = {
  fundamental_momentum: "動能",
  surprise: "驚喜",
  market_confirmation: "市場",
  quality: "品質",
};

const RATING_CLASS: Record<string, string> = {
  強力看多: "text-emerald-700 dark:text-emerald-300",
  看多: "text-emerald-600 dark:text-emerald-400",
  中性: "text-ink-soft",
  看空: "text-rose-600 dark:text-rose-400",
  強力看空: "text-rose-700 dark:text-rose-300",
};

type Props = {
  searchParams: Promise<{ conviction?: string; tier?: string }>;
};

export default async function SignalsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const conviction = sp.conviction || "";
  const tier = sp.tier || "";

  const since = new Date();
  since.setUTCDate(since.getUTCDate() - 30);

  const rows = await listEarningsSince(since, { limit: 80, maxTier: 5 });
  const { holdingsSet, watchlistSet } = getPortfolioTierSets();

  let items = rows
    .filter((r) => r.investment_signal?.score != null)
    .map((r) => {
      const sig = r.investment_signal!;
      const top = [...(sig.factors || [])]
        .filter((f) => f.available)
        .sort((a, b) => b.weight - a.weight)[0];
      return {
        report_id: r.report_id,
        ticker: r.ticker,
        quarter_label: r.quarter_label,
        score: sig.score as number,
        rating: sig.rating,
        conviction: sig.conviction,
        top_factor: top?.name ?? "—",
        portfolio_tier: classifyTier(r.ticker, holdingsSet, watchlistSet),
      };
    });

  if (conviction === "medium") {
    items = items.filter((i) => i.conviction === "medium" || i.conviction === "high");
  } else if (conviction === "high") {
    items = items.filter((i) => i.conviction === "high");
  }

  if (tier === "holding") {
    items = items.filter((i) => i.portfolio_tier === "holding");
  } else if (tier === "watchlist") {
    items = items.filter((i) => i.portfolio_tier === "watchlist");
  }

  items.sort((a, b) => b.score - a.score);

  const topBuy = items.find((i) => i.score >= 60);
  const topAvoid = [...items].reverse().find((i) => i.score < 45);

  function filterHref(next: { conviction?: string; tier?: string }) {
    const params = new URLSearchParams();
    if (next.conviction) params.set("conviction", next.conviction);
    if (next.tier) params.set("tier", next.tier);
    const q = params.toString();
    return q ? `/signals?${q}` : "/signals";
  }

  function tierBadge(pt: PortfolioTier) {
    if (pt === "holding") {
      return (
        <span className="rounded bg-accent/15 px-1.5 py-0.5 font-sans text-meta text-accent">
          持倉
        </span>
      );
    }
    if (pt === "watchlist") {
      return (
        <span className="rounded border border-rule px-1.5 py-0.5 font-sans text-meta text-ink-faint">
          觀察
        </span>
      );
    }
    return null;
  }

  return (
    <div>
      <Kicker tone="accent">Signal Engine</Kicker>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-ink">投資訊號排行</h1>
      <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">
        近 30 日財報的綜合訊號（0–100），僅讀取既有 scorecard / trend / 市場反應 /
        比率欄位。非投資建議。
      </p>

      {(topBuy || topAvoid) && (
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {topBuy && (
            <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 font-sans text-body text-ink-soft">
              本期偏強：<strong className="text-ink">{topBuy.ticker}</strong>{" "}
              {topBuy.quarter_label} · {topBuy.score.toFixed(1)} · {topBuy.rating}
            </p>
          )}
          {topAvoid && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 font-sans text-body text-ink-soft">
              本期偏弱：<strong className="text-ink">{topAvoid.ticker}</strong>{" "}
              {topAvoid.quarter_label} · {topAvoid.score.toFixed(1)} · {topAvoid.rating}
            </p>
          )}
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-2 font-sans text-meta">
        <Link
          href={filterHref({ tier })}
          className={`rounded border px-2 py-1 ${!conviction ? "border-accent text-accent" : "border-rule text-ink-faint"}`}
        >
          全部信心
        </Link>
        <Link
          href={filterHref({ conviction: "medium", tier })}
          className={`rounded border px-2 py-1 ${conviction === "medium" ? "border-accent text-accent" : "border-rule text-ink-faint"}`}
        >
          中+高信心
        </Link>
        <Link
          href={filterHref({ conviction: "high", tier })}
          className={`rounded border px-2 py-1 ${conviction === "high" ? "border-accent text-accent" : "border-rule text-ink-faint"}`}
        >
          僅高信心
        </Link>
        <span className="mx-1 text-ink-faint">|</span>
        <Link
          href={filterHref({ conviction: conviction || undefined })}
          className={`rounded border px-2 py-1 ${!tier ? "border-accent text-accent" : "border-rule text-ink-faint"}`}
        >
          全部 tier
        </Link>
        <Link
          href={filterHref({ conviction: conviction || undefined, tier: "holding" })}
          className={`rounded border px-2 py-1 ${tier === "holding" ? "border-accent text-accent" : "border-rule text-ink-faint"}`}
        >
          持倉
        </Link>
      </div>

      <Hairline className="mt-6" />

      {items.length === 0 ? (
        <p className="mt-8 font-sans text-body text-ink-faint">
          尚無含 investment_signal 的近期財報（需 pipeline 重跑後寫入）。
        </p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] font-sans text-body">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-faint">
                <th className="pb-3 pr-4 font-normal">#</th>
                <th className="pb-3 pr-4 font-normal">代號</th>
                <th className="pb-3 pr-4 font-normal">季度</th>
                <th className="pb-3 pr-4 font-normal">分數</th>
                <th className="pb-3 pr-4 font-normal">評級</th>
                <th className="pb-3 pr-4 font-normal">信心</th>
                <th className="pb-3 font-normal">主因子</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row, idx) => (
                <tr
                  key={row.report_id}
                  className={`border-b border-rule/60 ${row.portfolio_tier === "holding" ? "bg-accent/5" : ""}`}
                >
                  <td className="py-3 pr-4 font-mono text-meta text-ink-faint">{idx + 1}</td>
                  <td className="py-3 pr-4">
                    <Link
                      href={`/earnings/${row.ticker}`}
                      className="font-medium text-ink hover:text-accent"
                    >
                      {row.ticker}
                    </Link>{" "}
                    {tierBadge(row.portfolio_tier)}
                  </td>
                  <td className="py-3 pr-4">
                    <Link
                      href={`/earnings/report/${encodeURIComponent(row.report_id)}`}
                      className="text-ink-soft hover:text-accent"
                    >
                      {row.quarter_label}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 font-mono font-semibold tabular-nums">
                    {row.score.toFixed(1)}
                  </td>
                  <td className={`py-3 pr-4 ${RATING_CLASS[row.rating] ?? ""}`}>{row.rating}</td>
                  <td className="py-3 pr-4 text-meta text-ink-soft">{row.conviction}</td>
                  <td className="py-3 text-meta text-ink-faint">
                    {FACTOR_LABELS[row.top_factor] ?? row.top_factor}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
