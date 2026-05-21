import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Hairline } from "@/components/Hairline";
import { listEarningsReports } from "@/lib/earnings-firestore";

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
            <p className="font-sans text-body font-medium text-ink">
              {row.quarter_label}
            </p>
            <p className="mt-1 font-sans text-meta text-ink-faint">
              申報 {row.published_at_iso?.slice(0, 10) ?? "—"} · {row.confidence}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
