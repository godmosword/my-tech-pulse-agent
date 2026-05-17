import Link from "next/link";
import { listLatestItems } from "@/lib/firestore";
import {
  categoryLabel,
  formatEditorialDate,
  formatScore,
} from "@/lib/digest";
import { Hairline } from "@/components/Hairline";
import { Kicker, MetaDot } from "@/components/Kicker";

export const revalidate = 300;

const ARCHIVE_WINDOW_DAYS = 14;

type Items = Awaited<ReturnType<typeof listLatestItems>>;

export default async function ArchivePage() {
  const since = new Date(Date.now() - ARCHIVE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const items = await listLatestItems({ limit: 200, since });

  const buckets = bucketByDay(items);

  return (
    <div className="space-y-12 pt-2">
      <header className="space-y-4">
        <Kicker>Archive · Last {ARCHIVE_WINDOW_DAYS} days</Kicker>
        <h1 className="font-serif text-[34px] leading-[1.1] tracking-[-0.02em] text-ink sm:text-hero">
          Today’s Paper, day by day.
        </h1>
        <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
          Sorted by delivered_at · most recent first
        </p>
        <Hairline />
      </header>

      {buckets.length === 0 && (
        <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
          No items yet.
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
                  <div className="flex items-baseline justify-between gap-4">
                    <h3 className="font-serif text-[17px] leading-snug text-ink sm:text-[19px]">
                      {item.title || item.entity || "Untitled"}
                    </h3>
                    <span className="shrink-0 font-mono text-meta tabular-nums text-ink-soft">
                      {item.score > 0 ? formatScore(item.score) : "—"}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
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
    const key = (item.delivered_at_iso ?? "").slice(0, 10) || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([dayIso, dayItems]) => ({ dayIso, items: dayItems }));
}
