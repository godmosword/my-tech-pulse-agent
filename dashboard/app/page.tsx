import { listLatestItems } from "@/lib/firestore";
import { buildDigest } from "@/lib/digest";
import { DigestHeader } from "@/components/DigestHeader";
import { DeepInsightCard } from "@/components/DeepInsightCard";
import { ThemeSection } from "@/components/ThemeSection";

// ISR: pipeline runs a few times daily; rebuild on next request after 5 min.
// /api/revalidate flushes this on-demand right after a pipeline run.
export const revalidate = 300;

export default async function HomePage() {
  const items = await listLatestItems({ limit: 80 });
  const view = buildDigest(items);

  const latestDelivered = items
    .map((i) => i.delivered_at_iso)
    .filter((iso): iso is string => Boolean(iso))
    .sort()
    .reverse()[0] ?? null;

  if (!items.length) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-10">
      <DigestHeader
        latestDeliveredIso={latestDelivered}
        totalShown={view.totalShown}
        averageScore={view.averageScore}
      />

      {view.deepInsights.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-muted">
            🧠 深度洞察
          </h2>
          <div className="space-y-4">
            {view.deepInsights.map((item) => (
              <DeepInsightCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}

      {view.themes.map(({ theme, items: themeItems }) => (
        <ThemeSection key={theme} theme={theme} items={themeItems} />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-12 text-center text-ink-muted dark:border-slate-700">
      <p className="text-lg">尚無資料</p>
      <p className="mt-2 text-sm">
        Firestore <code className="font-mono">tech_pulse_memory_items</code>{" "}
        為空 — 請確認 pipeline 已執行並寫入歸檔。
      </p>
    </div>
  );
}
