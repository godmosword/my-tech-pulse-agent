import type { Metadata } from "next";
import Link from "next/link";

import { DensePageShell } from "@/components/data/DensePageShell";
import { RatingBadge } from "@/components/data/RatingBadge";
import { SignalsTable } from "@/components/data/SignalsTable";
import { StatCard } from "@/components/data/StatCard";
import { listEarningsSince } from "@/lib/earnings-firestore";
import { classifyTier, type PortfolioTier } from "@/lib/portfolio-metrics";
import { getPortfolioTierSets } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "投資訊號排行",
  description: "依綜合投資訊號分數排序的近期財報。",
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
        portfolio_tier: classifyTier(r.ticker, holdingsSet, watchlistSet) as PortfolioTier,
        factors: (sig.factors ?? []).map((f) => ({
          name: f.name,
          score: f.score ?? null,
          available: f.available,
        })),
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

  return (
    <DensePageShell
      kicker="Signal Engine"
      title="投資訊號排行"
      description="近 30 日財報綜合訊號（0–100），僅讀既有 scorecard / trend / 市場反應 / 比率欄位。非投資建議。"
      source="Firestore earnings"
    >
      {(topBuy || topAvoid) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {topBuy && (
            <StatCard
              kicker="本期偏強"
              value={topBuy.score.toFixed(1)}
              unit="/ 100"
              footnote={`${topBuy.ticker} · ${topBuy.quarter_label}`}
            />
          )}
          {topAvoid && (
            <div className="section-band border-neg/30">
              <p className="font-sans text-meta text-ink-faint">本期偏弱</p>
              <p className="stat-hero text-neg">{topAvoid.score.toFixed(1)}</p>
              <p className="mt-1 font-sans text-body text-ink-soft">
                {topAvoid.ticker} · {topAvoid.quarter_label}
              </p>
              <RatingBadge rating={topAvoid.rating} conviction={topAvoid.conviction} />
            </div>
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

      {items.length === 0 ? (
        <p className="mt-8 font-sans text-body text-ink-faint">
          尚無含 investment_signal 的近期財報（需 pipeline 重跑後寫入）。
        </p>
      ) : (
        <div className="mt-6">
          <SignalsTable items={items} />
        </div>
      )}
    </DensePageShell>
  );
}
