import type { Metadata } from "next";
import Link from "next/link";
import { listLatestItems } from "@/lib/firestore";
import {
  bestTimestamp,
  categoryLabel,
  formatEditorialDate,
} from "@/lib/digest";
import {
  applyFilters,
  buildArchiveHref,
  monthLabel,
  parseFilterState,
} from "@/lib/archive-filters";
import { Hairline } from "@/components/Hairline";
import { Kicker, MetaDot } from "@/components/Kicker";
import { displayTitle } from "@/lib/types";
import { ClearFiltersLink } from "@/components/ClearFiltersLink";

/** Build 階段無 Firestore 憑證時避免 prerender 失敗。 */
export const dynamic = "force-dynamic";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "歸檔",
  description:
    "依 delivered_at 排序的科技脈搏專欄歸檔（標題公開；完整內文可登入閱讀）。",
};

const ARCHIVE_WINDOW_DAYS = 90;

type Items = Awaited<ReturnType<typeof listLatestItems>>;

export default async function ArchivePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const state = parseFilterState(await searchParams);
  const since = new Date(Date.now() - ARCHIVE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const items = await listLatestItems({ limit: 400, since });

  const filtered = applyFilters(items, state);
  const buckets = bucketByDay(filtered);

  return (
    <div className="pt-2">
      <header className="space-y-4">
        <Kicker>Archive · Last {ARCHIVE_WINDOW_DAYS} days</Kicker>
        <h1 className="font-serif text-[34px] leading-[1.1] tracking-[-0.02em] text-ink sm:text-hero">
          Today’s Paper, day by day.
        </h1>
        <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
          Sorted by delivered_at · most recent first
        </p>
        <Hairline />
        <ActiveFilters state={state} />
      </header>

      <div className="mt-10 space-y-12">
        {buckets.length === 0 && (
          <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
            {items.length === 0
              ? "No items yet."
              : "目前篩選沒有符合的文章。"}
          </p>
        )}

        {buckets.map(({ dayIso, items: dayItems }) => (
          <section key={dayIso} className="space-y-4">
            <h2 className="font-serif text-[22px] leading-tight tracking-[-0.018em] text-ink sm:text-[26px]">
              {formatEditorialDate(dayIso) || "Undated"}
            </h2>
            <Hairline />
            <ul className="divide-y divide-rule">
              {dayItems.map((item) => (
                <li key={item.id} className="py-4">
                  <Link
                    href={`/item/${encodeURIComponent(item.id)}`}
                    className="block space-y-2 hover:[&_h3]:underline"
                  >
                    <Kicker as="div" className="flex flex-wrap items-center">
                      <span>{kindLabel(item.kind)}</span>
                      {item.category && (
                        <>
                          <MetaDot />
                          <span>{categoryLabel(item.category)}</span>
                        </>
                      )}
                      {item.source_name && (
                        <>
                          <MetaDot />
                          <span>{item.source_name}</span>
                        </>
                      )}
                    </Kicker>
                    <h3 className="font-serif text-[17px] leading-snug text-ink sm:text-[19px]">
                      {displayTitle(item)}
                    </h3>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function ActiveFilters({
  state,
}: {
  state: ReturnType<typeof parseFilterState>;
}) {
  if (!state.category && !state.month) return null;
  return (
    <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
      <span>篩選中：</span>
      {state.category && (
        <span className="ml-2 text-ink">{categoryLabel(state.category)}</span>
      )}
      {state.month && (
        <span className="ml-2 text-ink">{monthLabel(state.month)}</span>
      )}
      <ClearFiltersLink
        href={buildArchiveHref(state, { category: null, month: null })}
        className="ml-3 text-ink-faint hover:text-accent"
      >
        清除
      </ClearFiltersLink>
    </p>
  );
}

function kindLabel(kind: Items[number]["kind"]): string {
  switch (kind) {
    case "deep_brief":
      return "Deep Insight";
    case "earnings":
      return "Earnings";
    default:
      return "Dispatch";
  }
}

interface DayBucket {
  /** ISO yyyy-mm-dd used for keying + sorting. */
  dayIso: string;
  items: Items;
}

function bucketByDay(items: Items): DayBucket[] {
  const groups = new Map<string, Items>();
  for (const item of items) {
    // Bucket by the article's actual publish day (fallback to delivered).
    // Backfilled rows where delivered_at = batch day would otherwise pile
    // up under the wrong calendar day.
    const key = bestTimestamp(item).slice(0, 10) || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  // Sort items inside each day by the same timestamp, newest first, so the
  // displayed order matches the kicker timestamps.
  for (const list of groups.values()) {
    list.sort((a, b) => bestTimestamp(b).localeCompare(bestTimestamp(a)));
  }
  return [...groups.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([dayIso, dayItems]) => ({ dayIso, items: dayItems }));
}
