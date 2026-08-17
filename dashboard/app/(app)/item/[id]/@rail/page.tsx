import { getItemById } from "@/lib/firestore";
import { categoryLabel, formatEditorialDate } from "@/lib/digest";
import { Kicker } from "@/components/Kicker";

export const dynamic = "force-dynamic";
export const revalidate = 600;

/**
 * Right-rail provenance card for /item/[id]. Mirrors the bottom-of-page
 * Meta block but compressed: kicker labels stacked, only the fields a reader
 * actually skims for during reading (kind, category, delivered date, source,
 * score). The original URL lives in the main column footer only.
 */
export default async function ItemRail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = await getItemById(decodeURIComponent(id));
  if (!item) return null;

  const rows: { label: string; value: string }[] = [
    { label: "Kind", value: kindLabel(item.kind) },
    { label: "Section", value: item.category ? categoryLabel(item.category) : "—" },
    {
      label: "Delivered",
      value: formatEditorialDate(item.delivered_at_iso) || "—",
    },
    { label: "Source", value: item.source_name || "—" },
    {
      label: "Score",
      value: item.score > 0 ? `${item.score.toFixed(1)} / 10` : "—",
    },
  ];

  return (
    <div className="space-y-6 font-sans text-meta">
      <Kicker>On this piece</Kicker>
      <dl className="space-y-4">
        {rows.map(({ label, value }) => (
          <div key={label}>
            <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-faint">
              {label}
            </dt>
            <dd className="mt-1 text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function kindLabel(kind: "instant_summary" | "deep_brief" | "earnings"): string {
  switch (kind) {
    case "deep_brief":
      return "Deep Insight";
    case "earnings":
      return "Earnings";
    default:
      return "Dispatch";
  }
}
