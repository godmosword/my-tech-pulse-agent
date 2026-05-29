import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Hairline } from "@/components/Hairline";
import { BackLink } from "@/components/BackLink";
import { Breadcrumb } from "@/components/Breadcrumb";
import { EarningsInsightPanel } from "@/components/EarningsInsightPanel";
import { FundamentalsCard } from "@/components/FundamentalsCard";
import { InvestmentSignalCard } from "@/components/InvestmentSignalCard";
import { PriceReactionCard } from "@/components/PriceReactionCard";
import { RelationshipsSection } from "@/components/RelationshipsSection";
import { listEarningsPeers, listEarningsReports } from "@/lib/earnings-firestore";
import { loadEarningsInsight } from "@/lib/earnings-portal";
import {
  loadClustersSnapshot,
  loadCompanyRelationships,
  marketContextForTicker,
} from "@/lib/relationship-data";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ ticker: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ticker } = await params;
  return { title: `${ticker.toUpperCase()} 財報` };
}

export default async function EarningsTickerPage({ params }: Props) {
  const { ticker } = await params;
  const symbol = ticker.toUpperCase();
  const rows = await listEarningsReports({ ticker: symbol, limit: 24 });

  if (!rows.length) {
    notFound();
  }

  const tier = rows[0]?.tier;
  const latest = rows[0];
  const peers =
    tier != null ? await listEarningsPeers(tier, symbol, 6) : [];
  const business = loadCompanyRelationships(symbol);
  const clusters = loadClustersSnapshot();
  const market = marketContextForTicker(symbol, clusters);
  const insight = await loadEarningsInsight(symbol);

  return (
    <div>
      <BackLink href="/earnings" label="返回財報列表" />
      <Breadcrumb
        items={[
          { label: "投資", href: "/invest" },
          { label: "財報", href: "/earnings" },
          { label: symbol },
        ]}
      />
      <h1 className="mt-4 font-serif text-3xl font-semibold text-ink">{symbol}</h1>
      <p className="mt-2 font-sans text-body text-ink-soft">
        {rows[0]?.company}
      </p>
      <Hairline className="mt-6" />

      <EarningsInsightPanel
        symbol={symbol}
        enabled={insight.enabled}
        reason={insight.reason}
        hint={insight.hint}
        report={insight.report}
        reportUrlPath={insight.report_url_path}
      />

      {latest?.price_reaction && (
        <PriceReactionCard reaction={latest.price_reaction} />
      )}

      <FundamentalsCard
        ratios={latest?.ratios}
        surpriseHistory={latest?.surprise_history}
        financialHealth={latest?.financial_health}
      />

      {latest?.investment_signal && (
        <InvestmentSignalCard signal={latest.investment_signal} />
      )}

      {business && (business.edges.length > 0 || market.correlated.length > 0) && (
        <RelationshipsSection
          business={business}
          correlated={market.correlated}
        />
      )}

      <ul className="mt-6 divide-y divide-rule">
        {rows.map((row) => (
          <li key={row.report_id} className="py-5">
            <Link
              href={`/earnings/report/${encodeURIComponent(row.report_id)}`}
              className="font-sans text-body font-medium text-ink hover:text-accent hover:underline"
            >
              {row.quarter_label}
            </Link>
            <p className="mt-1 font-sans text-meta text-ink-faint">
              申報 {row.published_at_iso?.slice(0, 10) ?? "—"} · {row.confidence}
              {row.scorecard?.headline_verdict
                ? ` · ${row.scorecard.headline_verdict}`
                : ""}
            </p>
          </li>
        ))}
      </ul>

      {peers.length > 0 && (
        <section className="mt-10">
          <h2 className="font-sans text-meta uppercase tracking-widest text-ink-faint">
            同 Tier {tier} 近期財報
          </h2>
          <ul className="mt-4 divide-y divide-rule">
            {peers.map((p) => (
              <li key={p.report_id} className="py-3 flex justify-between gap-4">
                <Link
                  href={`/earnings/report/${encodeURIComponent(p.report_id)}`}
                  className="font-sans text-body text-ink hover:text-accent"
                >
                  {p.ticker} · {p.quarter_label}
                </Link>
                <span className="font-sans text-meta text-ink-faint shrink-0">
                  {p.scorecard?.headline_verdict ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
