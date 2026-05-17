import { notFound } from "next/navigation";
import { getItemById } from "@/lib/firestore";
import {
  categoryLabel,
  formatEditorialDate,
  formatMetaDate,
  formatScore,
} from "@/lib/digest";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { DeepInsightCard } from "@/components/DeepInsightCard";
import { Hairline } from "@/components/Hairline";
import { Kicker, MetaDot } from "@/components/Kicker";

export const revalidate = 600;

export default async function ItemPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = await getItemById(decodeURIComponent(id));
  if (!item) notFound();

  if (item.kind === "deep_brief") {
    return (
      <article className="space-y-10 pt-2">
        <DeepInsightCard item={item} />
        <Meta item={item} />
      </article>
    );
  }

  const headline = item.title || item.entity || "Untitled";
  const cat = categoryLabel(item.category);
  const metaDate = formatMetaDate(
    item.published_at_iso || item.delivered_at_iso
  );

  return (
    <article className="space-y-7 pt-2">
      <header className="space-y-5">
        <Kicker as="div" className="flex flex-wrap items-center">
          <span>{cat}</span>
          {item.source_name && (
            <>
              <MetaDot />
              <span>{item.source_name}</span>
            </>
          )}
          {metaDate && (
            <>
              <MetaDot />
              <span>{metaDate}</span>
            </>
          )}
        </Kicker>
        <h1 className="font-serif text-[34px] leading-[1.12] tracking-[-0.02em] text-ink sm:text-hero">
          {headline}
        </h1>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <ConfidenceBadge item={item} />
          <span aria-hidden className="text-ink-faint">
            ·
          </span>
          <span className="font-mono text-meta tabular-nums text-ink-soft">
            {item.score > 0 ? `${formatScore(item.score)} / 10` : "—"}
          </span>
        </div>
        <Hairline />
      </header>

      {item.zh_summary && (
        <p className="font-sans text-[18px] leading-[1.6] text-ink">
          {item.zh_summary}
        </p>
      )}

      {item.summary && (
        <p className="whitespace-pre-line font-serif text-[17px] leading-[1.7] text-ink">
          {item.summary}
        </p>
      )}

      <Meta item={item} />
    </article>
  );
}

function Meta({ item }: { item: Awaited<ReturnType<typeof getItemById>> }) {
  if (!item) return null;
  const rows: Array<{ label: string; value: string; mono?: boolean }> = [
    { label: "Kind", value: item.kind, mono: true },
    { label: "Category", value: item.category || "—", mono: true },
    { label: "Entity", value: item.entity || "—" },
    { label: "Source", value: item.source_name || "—" },
    {
      label: "Published",
      value: formatEditorialDate(item.published_at_iso) || "—",
    },
    {
      label: "Delivered",
      value: formatEditorialDate(item.delivered_at_iso) || "—",
    },
    { label: "Score status", value: item.score_status, mono: true },
  ];

  return (
    <section className="space-y-4 border-t border-rule pt-6">
      <Kicker>Provenance</Kicker>
      <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
        {rows.map(({ label, value, mono }) => (
          <Row key={label} label={label} value={value} mono={mono} />
        ))}
      </dl>
      {item.source_url ? (
        <div>
          <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
            Original
          </dt>
          <dd className="mt-1">
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              className="break-all font-sans text-meta text-accent underline-offset-4 hover:underline"
            >
              {item.source_url}
            </a>
          </dd>
        </div>
      ) : null}
    </section>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
        {label}
      </dt>
      <dd
        className={`mt-1 ${mono ? "font-mono text-meta text-ink" : "font-sans text-body text-ink"}`}
      >
        {value}
      </dd>
    </div>
  );
}
