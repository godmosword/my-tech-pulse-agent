import { listLatestItems } from "@/lib/firestore";
import { buildDigest } from "@/lib/digest";
import { DigestHeader } from "@/components/DigestHeader";
import { DeepInsightCard } from "@/components/DeepInsightCard";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
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
    <div>
      <DigestHeader
        latestDeliveredIso={latestDelivered}
        totalShown={view.totalShown}
        averageScore={view.averageScore}
      />

      {view.deepInsights.length > 0 && (
        <section className="pt-2">
          <Kicker tone="accent">Deep Insights</Kicker>
          <Hairline className="mt-3" />
          <div className="divide-y divide-rule">
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
    <div className="border-y border-rule py-16 text-center">
      <p className="font-serif text-[22px] text-ink">尚無資料</p>
      <p className="mt-3 font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
        Firestore tech_pulse_memory_items is empty —
        confirm the pipeline has archived recent items.
      </p>
    </div>
  );
}
