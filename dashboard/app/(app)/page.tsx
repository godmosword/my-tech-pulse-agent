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
import { ThemeSection } from "@/components/ThemeSection";
import { listEarningsSince } from "@/lib/earnings-firestore";

/** Build 階段無 Firestore 憑證時避免 prerender 失敗。 */
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

  const { items, snapshots, usingStaleFallback, todayStart } =
    await loadTodayDigestData();
  const todayEarnings = await listEarningsSince(todayStart, { limit: 6 }).catch(
    () => [],
  );
  const view = resolveDigestView(items, snapshots);
  const latestDelivered = latestDeliveredIso(items);

  if (!items.length) {
    return <EmptyState />;
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

      {todayEarnings.length > 0 && (
        <section className="pt-4">
          <Kicker tone="accent">今日財報</Kicker>
          <Hairline className="mt-3" />
          <ul className="divide-y divide-rule">
            {todayEarnings.map((e) => (
              <li key={e.report_id} className="py-4">
                <Link
                  href={`/earnings/report/${encodeURIComponent(e.report_id)}`}
                  className="font-serif text-dek text-ink hover:text-accent hover:underline"
                >
                  {e.ticker} · {e.quarter_label}
                </Link>
                {e.investment_takeaway_zh && (
                  <p className="mt-2 font-sans text-body text-ink-soft line-clamp-2">
                    {e.investment_takeaway_zh}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

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

      {view.themes.map(({ theme, items: themeItems }) => (
        <ThemeSection
          key={theme}
          theme={theme}
          items={themeItems}
          authenticated={authenticated}
        />
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
        查看近期內容。
      </p>
    </div>
  );
}
