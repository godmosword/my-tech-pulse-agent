import type { Metadata } from "next";
import Link from "next/link";
import { getLatestDigestSnapshot, listLatestItems } from "@/lib/firestore";
import { resolveDigestView } from "@/lib/digest-snapshot";
import type { DigestSnapshotDoc } from "@/lib/digest-snapshot";
import { isPublicReadMode } from "@/lib/env-public-read";
import { getReaderSession } from "@/lib/session";
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

  // 1) Try "today" in Asia/Taipei first so the homepage reflects the latest
  //    Telegram dispatch. 2) Fall back to the most recent batch when today
  //    is empty (e.g. early morning before the pipeline runs) so the page
  //    is never blank.
  const todayStart = startOfTodayTaipeiUtc();
  let items = await listLatestItems({ limit: 80, since: todayStart });
  if (items.length === 0) {
    items = await listLatestItems({ limit: 80 });
  }
  const todayEarnings = await listEarningsSince(todayStart, { limit: 6 });
  const snapshot = await getLatestDigestSnapshot();
  const view = resolveDigestView(
    items,
    snapshot as DigestSnapshotDoc | null,
  );

  const latestDelivered = items
    .map((i) => i.delivered_at_iso)
    .filter((iso): iso is string => Boolean(iso))
    .sort()
    .reverse()[0] ?? null;

  if (!items.length) {
    return <EmptyState />;
  }

  return (
    <div>
      <DigestHeader
        latestDeliveredIso={latestDelivered}
        totalShown={view.totalShown}
      />

      {todayEarnings.length > 0 && (
        <section className="pt-4">
          <Kicker tone="accent">今日財報</Kicker>
          <Hairline className="mt-3" />
          <ul className="divide-y divide-rule">
            {todayEarnings.map((e) => (
              <li key={e.report_id} className="py-4">
                <Link
                  href={`/earnings/report/${encodeURIComponent(e.report_id)}`}
                  className="font-serif text-xl text-ink hover:text-accent hover:underline"
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

/** Returns the UTC instant that corresponds to 00:00 today in Asia/Taipei. */
function startOfTodayTaipeiUtc(): Date {
  // Asia/Taipei is a fixed UTC+8 offset (no DST), so we can derive the wall
  // date with toLocaleDateString and rebuild the boundary in UTC directly.
  const todayTpe = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Taipei",
  }); // "YYYY-MM-DD"
  // 00:00 Asia/Taipei == 16:00 UTC the previous day.
  return new Date(`${todayTpe}T00:00:00+08:00`);
}

function EmptyState() {
  return (
    <div className="border-y border-rule py-16 text-center">
      <p className="font-serif text-[22px] text-ink">今日尚無上線內容</p>
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
