import type { Metadata } from "next";
import Link from "next/link";

import { BackLink } from "@/components/BackLink";
import { StatCard } from "@/components/data/StatCard";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
import { formatRelativeDateline } from "@/lib/digest";
import { listLatestItems } from "@/lib/firestore";
import {
  KIND_LABEL,
  PRIORITY_TIER_LABEL,
  summarizeHealth,
  HEALTH_SAMPLE_LIMIT,
} from "@/lib/summarizeHealth";
import { displayTitle, PRIORITY_DOT_CLASS, priorityLevel } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "營運摘要",
  description: "已上線讀者內容的數量與品質分佈摘要。",
};

export default async function HealthPage() {
  let summary;
  try {
    const items = await listLatestItems({ limit: HEALTH_SAMPLE_LIMIT });
    summary = summarizeHealth(items);
  } catch {
    return (
      <div className="pt-2">
        <BackLink href="/" label="返回 Today" />
        <header className="mt-4 space-y-4">
          <Kicker>營運摘要</Kicker>
          <h1 className="font-serif text-editorial-title text-ink">營運摘要</h1>
          <Hairline />
        </header>
        <p className="mt-10 font-sans text-body text-ink-soft">
          暫時無法載入內容摘要，請重新整理頁面後再試。
        </p>
      </div>
    );
  }

  if (!summary.delivered.length) {
    return (
      <div className="pt-2">
        <BackLink href="/" label="返回 Today" />
        <header className="mt-4 space-y-4">
          <Kicker>營運摘要</Kicker>
          <h1 className="font-serif text-editorial-title text-ink">營運摘要</h1>
          <p className="font-sans text-body text-ink-soft">
            已上線讀者內容的整理摘要，非後台設定頁。
          </p>
          <Hairline />
        </header>
        <p className="mt-10 font-sans text-body text-ink-soft">尚無上線紀錄。</p>
      </div>
    );
  }

  const latestLabel = summary.latestDeliveredAtIso
    ? formatRelativeDateline(summary.latestDeliveredAtIso)
    : "—";

  return (
    <div className="pt-2">
      <BackLink href="/" label="返回 Today" />
      <header className="mt-4 space-y-4">
        <Kicker>營運摘要</Kicker>
        <h1 className="font-serif text-editorial-title text-ink">營運摘要</h1>
        <p className="font-sans text-body text-ink-soft">
          已上線讀者內容的整理摘要，非後台設定頁。
        </p>
        <Hairline />
      </header>

      {summary.lowSample && (
        <p className="mt-6 font-sans text-meta text-ink-faint">
          樣本較少，僅供參考（近 {HEALTH_SAMPLE_LIMIT} 筆內僅 {summary.delivered.length}{" "}
          則已上線）。
        </p>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard kicker="內容最近一次上線" value={latestLabel} />
        <StatCard
          kicker="近 24 小時"
          value={summary.countLast24h}
          unit="則"
          footnote={`近 7 天 ${summary.countLast7d} 則`}
        />
        <StatCard
          kicker="類型分佈 · 近 7 天"
          value={`快訊 ${summary.kindCounts.instant_summary}`}
          footnote={`深度 ${summary.kindCounts.deep_brief} · 財報 ${summary.kindCounts.earnings}`}
        />
        <StatCard
          kicker="品質分佈 · 近 7 天"
          value={`偏高 ${summary.priorityCounts.high}`}
          footnote={`中等 ${summary.priorityCounts.med} · 偏低 ${summary.priorityCounts.low}`}
        />
      </div>

      <p className="mt-4 font-sans text-meta text-ink-faint">
        分數由編輯流程自動標記，僅供內部參考。
      </p>

      <section className="mt-10 space-y-4">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          近期上線
        </h2>
        <Hairline />
        <ul className="divide-y divide-rule">
          {summary.delivered.slice(0, 30).map((row) => {
            const tier = priorityLevel(row.score);
            return (
              <li key={row.id} className="py-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
                  <div className="min-w-0 flex-1 space-y-1">
                    <Link
                      href={`/item/${encodeURIComponent(row.id)}`}
                      className="font-serif text-[18px] leading-snug text-ink hover:text-accent"
                    >
                      {displayTitle(row)}
                    </Link>
                    <p className="font-sans text-meta text-ink-faint">
                      {row.source_name || "—"} · {KIND_LABEL[row.kind]}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 font-sans text-meta text-ink-soft">
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${PRIORITY_DOT_CLASS[tier]}`}
                        aria-hidden
                      />
                      <span>
                        {PRIORITY_TIER_LABEL[tier]} · {row.score.toFixed(1)}
                      </span>
                    </span>
                    <span>{formatRelativeDateline(row.delivered_at_iso)}</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
