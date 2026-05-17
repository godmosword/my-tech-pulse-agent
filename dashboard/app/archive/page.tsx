import Link from "next/link";
import { listLatestItems } from "@/lib/firestore";
import { formatRelativeDate, formatScore } from "@/lib/digest";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

export const revalidate = 300;

const ARCHIVE_WINDOW_DAYS = 14;

export default async function ArchivePage() {
  const since = new Date(Date.now() - ARCHIVE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const items = await listLatestItems({ limit: 200, since });

  const buckets = bucketByDay(items);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">時間軸</h1>
        <p className="mt-1 text-sm text-ink-muted">
          近 {ARCHIVE_WINDOW_DAYS} 天歸檔（依 delivered_at 倒序）
        </p>
      </header>

      {buckets.length === 0 && (
        <p className="text-sm text-ink-muted">尚無資料</p>
      )}

      {buckets.map(({ day, items: dayItems }) => (
        <section key={day} className="space-y-3">
          <h2 className="text-sm font-semibold text-ink-muted">{day}</h2>
          <ul className="divide-y divide-slate-200/60 rounded-md border border-slate-200/60 bg-surface-alt dark:divide-slate-700/40 dark:border-slate-700/40 dark:bg-slate-900/40">
            {dayItems.map((item) => (
              <li key={item.id} className="px-4 py-3">
                <Link
                  href={`/item/${encodeURIComponent(item.id)}`}
                  className="flex flex-col gap-1 hover:underline"
                >
                  <div className="flex items-center gap-2 text-xs text-ink-subtle">
                    <span className="font-mono">
                      {item.kind === "deep_brief"
                        ? "🧠"
                        : item.kind === "earnings"
                          ? "📊"
                          : "⭐"}{" "}
                      {item.score > 0 ? formatScore(item.score) : "—"}
                    </span>
                    <ConfidenceBadge item={item} />
                    {item.delivered_at_iso && (
                      <span>· {formatRelativeDate(item.delivered_at_iso)}</span>
                    )}
                  </div>
                  <span className="text-sm font-medium">
                    {item.title || item.entity || "Untitled"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

interface DayBucket {
  day: string;
  items: Awaited<ReturnType<typeof listLatestItems>>;
}

function bucketByDay(
  items: Awaited<ReturnType<typeof listLatestItems>>
): DayBucket[] {
  const groups = new Map<string, DayBucket["items"]>();
  for (const item of items) {
    const key = (item.delivered_at_iso ?? "").slice(0, 10) || "未知";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([day, dayItems]) => ({ day, items: dayItems }));
}
