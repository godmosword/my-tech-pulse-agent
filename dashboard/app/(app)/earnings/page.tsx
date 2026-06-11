import type { Metadata } from "next";

import { BackLink } from "@/components/BackLink";
import { Breadcrumb } from "@/components/Breadcrumb";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
import { EarningsList } from "@/components/earnings/EarningsList";
import { listEarningsReports } from "@/lib/earnings-firestore";
import { encodeEarningsCursor } from "@/lib/pagination-cursor";

export const dynamic = "force-dynamic";
export const revalidate = 300;

export const metadata: Metadata = {
  title: "財報",
  description: "美股 AI 半導體財報雷達：以 SEC 申報時間排序的結構化季報指標。",
};

const EARNINGS_PAGE_SIZE = 40;

export default async function EarningsPage() {
  const rows = await listEarningsReports({ limit: EARNINGS_PAGE_SIZE, maxTier: 5 });
  const last = rows.at(-1);
  const initialNextCursor =
    last && rows.length === EARNINGS_PAGE_SIZE && last.published_at_iso
      ? encodeEarningsCursor({
          publishedAtIso: last.published_at_iso,
          reportId: last.report_id,
        })
      : null;

  return (
    <div>
      <BackLink href="/invest" label="返回投資中樞" />
      <Breadcrumb
        items={[
          { label: "投資", href: "/invest" },
          { label: "財報" },
        ]}
      />
      <Kicker tone="accent">Earnings Radar</Kicker>
      <h1 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-ink">
        財報雷達
      </h1>
      <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">
        以 SEC 申報時間（published_at）排序；季度標籤依各公司 fiscal
        calendar，不以日曆季推斷。
      </p>
      <Hairline className="mt-6" />

      <EarningsList
        initialItems={rows}
        initialNextCursor={initialNextCursor}
        pageSize={EARNINGS_PAGE_SIZE}
      />
    </div>
  );
}
