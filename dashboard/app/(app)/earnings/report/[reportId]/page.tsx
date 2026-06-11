import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Hairline } from "@/components/Hairline";
import { BackLink } from "@/components/BackLink";
import { Breadcrumb } from "@/components/Breadcrumb";
import { EarningsReportEmpty } from "@/components/earnings/EarningsReportEmpty";
import { EarningsReportMarkdown } from "@/components/earnings/EarningsReportMarkdown";
import { SurpriseBadge } from "@/components/earnings/SurpriseBadge";
import { getEarningsReport } from "@/lib/earnings-firestore";
import { hasRenderableMarkdown } from "@/lib/earnings-report-markdown";

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

export default async function EarningsReportPage({ params }: Props) {
  const { reportId } = await params;
  const row = await getEarningsReport(decodeURIComponent(reportId));
  if (!row) notFound();

  const sc = row.scorecard;
  const markdown = row.rendered_markdown_zh;

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
          <SurpriseBadge
            label="營收驚喜"
            surprise={sc.revenue?.surprise_pct}
            basis={sc.revenue?.accounting_basis}
          />
          <SurpriseBadge
            label="EPS驚喜"
            surprise={sc.eps?.surprise_pct}
            basis={sc.eps?.accounting_basis}
          />
        </div>
      )}

      <Hairline className="mt-6" />

      {hasRenderableMarkdown(markdown) ? (
        <EarningsReportMarkdown content={markdown!.trim()} />
      ) : (
        <EarningsReportEmpty ticker={row.ticker} />
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
