import Link from "next/link";

import { categoryLabel } from "@/lib/digest";
import { buildArchiveHref } from "@/lib/archive-filters";
import {
  type RenderableItem,
} from "@/lib/types";

import { Kicker } from "./Kicker";

interface Props {
  items: RenderableItem[];
}

const CATEGORY_DOT: Record<string, string> = {
  product_launch: "bg-emerald-500",
  funding: "bg-amber-500",
  acquisition: "bg-violet-500",
  earnings: "bg-sky-500",
  regulation: "bg-rose-500",
  research: "bg-indigo-500",
  other: "bg-ink-faint",
};

const EMPTY_FILTER = { category: null, month: null, ticker: null };

/** Right-rail dashboard for the homepage. Aggregates today's items into two
 *  glanceable groups: category counts and top mentioned tickers.
 *  Category rows link to /archive with the corresponding filter. */
export function TodayRail({ items }: Props) {
  const categoryRows = aggregateCategories(items);
  const tickerRows = aggregateTickers(items);

  return (
    <aside className="space-y-8 font-sans text-meta">
      <Section kicker="今日分類">
        {categoryRows.length === 0 ? (
          <EmptyLine label="尚無分類資料" />
        ) : (
          <ul className="space-y-1.5">
            {categoryRows.map((row) => (
              <li key={row.value}>
                <Link
                  href={buildArchiveHref(EMPTY_FILTER, { category: row.value })}
                  className="flex items-baseline justify-between gap-2 text-ink-soft hover:text-accent"
                >
                  <span className="flex items-center gap-2 truncate">
                    <span
                      aria-hidden="true"
                      className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                        CATEGORY_DOT[row.value] ?? "bg-ink-faint"
                      }`}
                    />
                    <span className="truncate">{row.label}</span>
                  </span>
                  <span className="shrink-0 tabular-nums text-ink-faint">
                    {row.count}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section kicker="今日熱門代號">
        {tickerRows.length === 0 ? (
          <EmptyLine label="今日未提及任何上市代號" />
        ) : (
          <ul className="flex flex-wrap gap-2">
            {tickerRows.map((row) => (
              <li key={row.value}>
                <Link
                  href={buildArchiveHref(EMPTY_FILTER, { ticker: row.value })}
                  className="flex items-baseline gap-1 rounded-sm border border-rule px-2 py-1 hover:border-accent hover:text-accent"
                >
                  <span className="font-mono text-[12px] text-ink">{row.value}</span>
                  <span className="font-mono text-[11px] tabular-nums text-ink-faint">
                    ×{row.count}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

    </aside>
  );
}

function Section({
  kicker,
  children,
}: {
  kicker: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <Kicker as="div">{kicker}</Kicker>
      {children}
    </div>
  );
}

function EmptyLine({ label }: { label: string }) {
  return <p className="text-ink-faint">{label}</p>;
}

interface CategoryRow {
  value: string;
  label: string;
  count: number;
}

function aggregateCategories(items: RenderableItem[]): CategoryRow[] {
  const counts = new Map<string, number>();
  for (const it of items) {
    const c = (it.category || "").toLowerCase();
    if (!c) continue;
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, label: categoryLabel(value), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

interface TickerRow {
  value: string;
  count: number;
}

function aggregateTickers(items: RenderableItem[]): TickerRow[] {
  const counts = new Map<string, number>();
  for (const it of items) {
    for (const t of it.tickers ?? []) {
      const key = t.trim().toUpperCase();
      if (!key) continue;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
    .slice(0, 5);
}

