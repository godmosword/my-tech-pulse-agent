import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Hairline } from "@/components/Hairline";
import { PriceReactionCard } from "@/components/PriceReactionCard";
import { listEarningsPeers, listEarningsReports } from "@/lib/earnings-firestore";

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
  const peers =
    tier != null ? await listEarningsPeers(tier, symbol, 6) : [];

  return (
    <div>
      <Link
        href="/earnings"
        className="font-sans text-meta uppercase tracking-widest text-ink-faint hover:text-accent"
      >
        ← 財報雷達
      </Link>
      <h1 className="mt-4 font-serif text-3xl font-semibold text-ink">{symbol}</h1>
      <p className="mt-2 font-sans text-body text-ink-soft">
        {rows[0]?.company}
      </p>
      <Hairline className="mt-6" />
      <ul className="divide-y divide-rule">
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
