import type { Metadata } from "next";
import Link from "next/link";
import { resolveDigestView } from "@/lib/digest-snapshot";
import { isPublicReadMode } from "@/lib/env-public-read";
import { getReaderSession } from "@/lib/session";
import {
  latestDeliveredIso,
  loadTodayDigestData,
} from "@/lib/today-digest";
import { AttentionTriage } from "@/components/AttentionTriage";
import { DigestHeader } from "@/components/DigestHeader";
import { DeepInsightCard } from "@/components/DeepInsightCard";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
import { Reveal } from "@/components/Reveal";
import { ThemeSection } from "@/components/ThemeSection";
import { PortfolioTierBadge } from "@/components/data/PortfolioTierBadge";
import {
  listEarningsReports,
  type EarningsReportRow,
} from "@/lib/earnings-firestore";
import {
  withPortfolioTierOnReports,
  type PortfolioTier,
} from "@/lib/portfolio-server";

/** Avoid static prerender of live digest JSON. */
export const dynamic = "force-dynamic";

// ISR: pipeline runs a few times daily; rebuild on next request after 5 min.
// /api/revalidate flushes this on-demand right after a pipeline run.
export const revalidate = 300;

export const metadata: Metadata = {
  title: "今日",
  description:
    "科技脈搏每日編輯精選：深度洞見與主題分組快訊（公開摘要；完整正文可登入閱讀）。",
};

export default async function HomePage() {
  const authenticated =
    !isPublicReadMode() || (await getReaderSession()) !== null;

  const { items, snapshots, usingStaleFallback } = await loadTodayDigestData();
  const publishedEarnings = withPortfolioTierOnReports(
    await listEarningsReports({ limit: 6 }).catch(() => []),
  );
  const view = resolveDigestView(items, snapshots);
  const latestDelivered = latestDeliveredIso(items);

  if (!items.length) {
    return (
      <div>
        <EmptyState />
        <PublishedEarnings reports={publishedEarnings} />
      </div>
    );
  }

  if (view.totalShown === 0) {
    return (
      <div>
        <DigestHeader
          latestDeliveredIso={latestDelivered}
          totalShown={0}
          usingStaleFallback={usingStaleFallback}
        />
        <div className="border-y border-rule py-12 text-center">
          <p className="font-serif text-editorial-headline text-ink">尚無可顯示的精選內容</p>
          <p className="mt-3 font-sans text-body text-ink-soft">
            已 delivery 的項目可能分數過低或未通過品質閾值。可先瀏覽{" "}
            <Link
              href="/archive"
              className="text-accent underline-offset-4 hover:underline"
            >
              歸檔
            </Link>
            。
          </p>
        </div>
        <PublishedEarnings reports={publishedEarnings} />
      </div>
    );
  }

  return (
    <div>
      <DigestHeader
        latestDeliveredIso={latestDelivered}
        totalShown={view.totalShown}
        usingStaleFallback={usingStaleFallback}
      />

      <AttentionTriage />

      <PublishedEarnings reports={publishedEarnings} />

      {view.deepInsights.length > 0 && (
        <section className="pt-2">
          <Kicker tone="accent">深度洞見</Kicker>
          <Hairline className="mt-3" />
          <div className="divide-y divide-rule">
            {view.deepInsights.map((item) => (
              <DeepInsightCard
                key={item.id}
                item={item}
                authenticated={authenticated}
                returnToPath={`/item/${encodeURIComponent(item.id)}`}
              />
            ))}
          </div>
        </section>
      )}

      {view.themes.map(({ theme, items: themeItems }, i) => (
        <Reveal key={theme} delayMs={Math.min(i, 4) * 60}>
          <ThemeSection
            theme={theme}
            items={themeItems}
            authenticated={authenticated}
          />
        </Reveal>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="border-y border-rule py-16 text-center">
      <p className="font-serif text-editorial-headline text-ink">今日尚無上線內容</p>
      <p className="mt-3 font-sans text-body text-ink-soft">
        每日 pipeline 完成後，新稿會自動出現在此。您也可以先瀏覽{" "}
        <Link href="/archive" className="text-accent underline-offset-4 hover:underline">
          歸檔
        </Link>
        或{" "}
        <Link href="/earnings" className="text-accent underline-offset-4 hover:underline">
          已公布財報
        </Link>
        。
      </p>
    </div>
  );
}

function PublishedEarnings({
  reports,
}: {
  reports: Array<EarningsReportRow & { portfolio_tier: PortfolioTier }>;
}) {
  return (
    <section className="pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Kicker tone="accent">已公布財報</Kicker>
        <Link
          href="/earnings"
          className="font-sans text-meta text-accent underline-offset-4 hover:underline"
        >
          查看全部
        </Link>
      </div>
      <Hairline className="mt-3" />
      {reports.length === 0 ? (
        <p className="py-6 font-sans text-body text-ink-soft">
          尚無已歸檔財報。可先前往{" "}
          <Link
            href="/earnings"
            className="text-accent underline-offset-4 hover:underline"
          >
            財報雷達
          </Link>
          。
        </p>
      ) : (
        <ul className="divide-y divide-rule">
          {reports.map((e) => (
            <li key={e.report_id} className="py-4">
              <span className="flex flex-wrap items-baseline gap-2">
                <Link
                  href={`/earnings/${encodeURIComponent(e.ticker)}`}
                  className="font-mono text-meta text-ink hover:text-accent hover:underline"
                >
                  {e.ticker}
                </Link>
                <Link
                  href={`/earnings/report/${encodeURIComponent(e.report_id)}`}
                  className="font-serif text-dek text-ink hover:text-accent hover:underline"
                >
                  {e.quarter_label}
                </Link>
                <PortfolioTierBadge tier={e.portfolio_tier} />
              </span>
              {e.investment_takeaway_zh && (
                <p className="mt-2 font-sans text-body text-ink-soft line-clamp-2">
                  {e.investment_takeaway_zh}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
