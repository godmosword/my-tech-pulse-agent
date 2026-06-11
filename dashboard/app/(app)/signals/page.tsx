import type { Metadata } from "next";
import Link from "next/link";

import { BackfillCode, BackfillHint } from "@/components/data/BackfillHint";
import { DensePageShell } from "@/components/data/DensePageShell";
import { RatingBadge } from "@/components/data/RatingBadge";
import {
  SignalsListSection,
  type SignalTableItem,
} from "@/components/data/SignalsListSection";
import { StatCard } from "@/components/data/StatCard";
import { listSignalsPage } from "@/lib/signals-list-page";
import { getPortfolioTierSets } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "投資訊號排行",
  description: "依綜合投資訊號分數排序的近期財報。",
};

const SIGNALS_PAGE_SIZE = 40;
const SIGNALS_DAYS = 30;

type Props = {
  searchParams: Promise<{ conviction?: string; tier?: string }>;
};

export default async function SignalsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const conviction = sp.conviction || "";
  const tier = sp.tier || "";

  const { holdingsSet, watchlistSet } = getPortfolioTierSets();
  const page = await listSignalsPage(
    {
      days: SIGNALS_DAYS,
      minConviction: conviction || undefined,
      tierFilter: tier || undefined,
      limit: SIGNALS_PAGE_SIZE,
    },
    holdingsSet,
    watchlistSet,
  );

  const items: SignalTableItem[] = page.items.map((item) => ({
    report_id: item.report_id,
    ticker: item.ticker,
    quarter_label: item.quarter_label,
    score: item.score,
    rating: item.rating,
    conviction: item.conviction,
    top_factor: item.top_factor ?? "—",
    portfolio_tier: item.portfolio_tier,
    factors: item.factors,
  }));

  const topBuy = items.find((i) => i.score >= 60);
  const topAvoid = [...items].reverse().find((i) => i.score < 45);

  function filterHref(next: { conviction?: string; tier?: string }) {
    const params = new URLSearchParams();
    if (next.conviction) params.set("conviction", next.conviction);
    if (next.tier) params.set("tier", next.tier);
    const q = params.toString();
    return q ? `/signals?${q}` : "/signals";
  }

  const filterKey = [conviction, tier].join("|");

  return (
    <DensePageShell
      kicker="Signal Engine"
      title="投資訊號排行"
      description="近 30 日財報綜合訊號（0–100），僅讀既有 scorecard / trend / 市場反應 / 比率欄位。非投資建議。"
      source="Firestore earnings"
      backHref="/invest"
      backLabel="返回投資中樞"
      breadcrumb={[
        { label: "投資", href: "/invest" },
        { label: "訊號" },
      ]}
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
        <BackfillHint
          title="尚無含 investment_signal 的近期財報"
          note="Vercel 部署讀 Firestore；本機 dashboard 需 ADC 與同一 GCP 專案。既有舊報告若缺 signal，需用 backfill 重寫。"
        >
          <p>1. 新財報（Cloud Run 排程或本機完整 pipeline）：</p>
          <BackfillCode>{`cd /path/to/my-tech-pulse-agent
python main.py`}</BackfillCode>
          <p>2. 依 SEC 申報日區間 backfill（寫入 Firestore 並附 investment_signal）：</p>
          <BackfillCode>{`python scripts/backfill_earnings.py \\
  --since 2026-01-01 --until 2026-05-21 \\
  --max-filings 20`}</BackfillCode>
          <p>環境：SEC_USER_AGENT、Firestore ADC（GOOGLE_APPLICATION_CREDENTIALS 或 gcloud auth）。</p>
        </BackfillHint>
      ) : (
        <SignalsListSection
          key={filterKey}
          initialItems={items}
          initialNextCursor={page.nextCursor}
          pageSize={SIGNALS_PAGE_SIZE}
          days={SIGNALS_DAYS}
          conviction={conviction}
          tier={tier}
        />
      )}
    </DensePageShell>
  );
}
