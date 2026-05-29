import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Hairline } from "@/components/Hairline";
import { BackLink } from "@/components/BackLink";
import { Breadcrumb } from "@/components/Breadcrumb";
import { Kicker } from "@/components/Kicker";
import { getEarningsReport } from "@/lib/earnings-firestore";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ reportId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { reportId } = await params;
  const row = await getEarningsReport(decodeURIComponent(reportId));
  if (!row) return { title: "找不到財報" };
  return {
    title: `${row.ticker} ${row.quarter_label} 財報深度解析`,
    description: row.investment_takeaway_zh || `${row.company} 財報深度報告`,
  };
}

function surpriseBadge(surprise: number | null | undefined, basis?: string) {
  if (basis === "Mixed") {
    return (
      <span className="rounded border border-amber-500/40 px-2 py-0.5 text-meta text-amber-700 dark:text-amber-300">
        基準不一致
      </span>
    );
  }
  if (surprise == null || !Number.isFinite(surprise)) return null;
  const pos = surprise > 0;
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-meta ${
        pos ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "bg-red-500/15 text-red-700 dark:text-red-300"
      }`}
    >
      {pos ? "🟢" : "🔴"} {surprise > 0 ? "+" : ""}
      {surprise.toFixed(1)}%
    </span>
  );
}

export default async function EarningsReportPage({ params }: Props) {
  const { reportId } = await params;
  const row = await getEarningsReport(decodeURIComponent(reportId));
  if (!row) notFound();

  const sc = row.scorecard;

  return (
    <div>
      <BackLink
        href={`/earnings/${encodeURIComponent(row.ticker)}`}
        label={`返回 ${row.ticker} 財報`}
      />
      <Breadcrumb
        items={[
          { label: "投資", href: "/invest" },
          { label: "財報", href: "/earnings" },
          { label: "報告" },
        ]}
      />
      <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <h1 className="font-serif text-3xl font-semibold text-ink">
          {row.ticker} {row.quarter_label}
        </h1>
        {row.tier != null && (
          <span className="font-sans text-meta text-ink-faint">Tier {row.tier}</span>
        )}
        {sc?.headline_verdict && (
          <span className="font-sans text-body text-ink-soft">{sc.headline_verdict}</span>
        )}
      </div>
      <p className="mt-2 font-sans text-body text-ink-soft">{row.company}</p>

      {sc && (
        <div className="mt-4 flex flex-wrap gap-2">
          {surpriseBadge(sc.revenue?.surprise_pct, sc.revenue?.accounting_basis)}
          {surpriseBadge(sc.eps?.surprise_pct, sc.eps?.accounting_basis)}
        </div>
      )}

      <Hairline className="mt-6" />

      {row.rendered_markdown_zh ? (
        <article className="prose prose-neutral mt-6 max-w-none font-sans text-body text-ink dark:prose-invert">
          <pre className="whitespace-pre-wrap font-sans text-[15px] leading-relaxed">
            {row.rendered_markdown_zh}
          </pre>
        </article>
      ) : (
        <p className="mt-6 text-body text-ink-soft">尚無深度報告正文。</p>
      )}

      {row.source_url && (
        <p className="mt-8">
          <a
            href={row.source_url}
            className="font-sans text-meta text-accent hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            SEC filing ↗
          </a>
        </p>
      )}
    </div>
  );
}
