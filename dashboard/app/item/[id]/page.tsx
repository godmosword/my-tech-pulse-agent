import { notFound } from "next/navigation";
import { getItemById } from "@/lib/firestore";
import { formatRelativeDate, formatScore } from "@/lib/digest";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { DeepInsightCard } from "@/components/DeepInsightCard";

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
      <div className="space-y-6">
        <DeepInsightCard item={item} />
        <Meta item={item} />
      </div>
    );
  }

  return (
    <article className="space-y-5">
      <header>
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <span className="font-mono">
            {item.kind === "earnings" ? "📊" : "⭐"}{" "}
            {item.score > 0 ? formatScore(item.score) : "—"}
          </span>
          <ConfidenceBadge item={item} />
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {item.title || item.entity || "Untitled"}
        </h1>
      </header>

      {item.summary && (
        <p className="whitespace-pre-line text-base leading-relaxed text-ink">
          {item.summary}
        </p>
      )}

      <Meta item={item} />
    </article>
  );
}

function Meta({ item }: { item: Awaited<ReturnType<typeof getItemById>> }) {
  if (!item) return null;
  return (
    <dl className="grid grid-cols-1 gap-2 rounded-md border border-slate-200/60 bg-surface-alt p-4 text-sm dark:border-slate-700/40 dark:bg-slate-900/40 sm:grid-cols-2">
      <Row label="kind" value={item.kind} mono />
      <Row label="category" value={item.category || "—"} mono />
      <Row label="entity" value={item.entity || "—"} />
      <Row label="source_name" value={item.source_name || "—"} />
      <Row
        label="published_at"
        value={
          item.published_at_iso
            ? formatRelativeDate(item.published_at_iso)
            : "—"
        }
      />
      <Row
        label="delivered_at"
        value={
          item.delivered_at_iso
            ? formatRelativeDate(item.delivered_at_iso)
            : "—"
        }
      />
      <Row label="score_status" value={item.score_status} mono />
      {item.source_url ? (
        <div className="sm:col-span-2">
          <dt className="text-xs uppercase tracking-wider text-ink-subtle">
            原文
          </dt>
          <dd className="mt-1">
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              className="break-all text-indigo-700 hover:underline dark:text-indigo-300"
            >
              {item.source_url}
            </a>
          </dd>
        </div>
      ) : null}
    </dl>
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
      <dt className="text-xs uppercase tracking-wider text-ink-subtle">
        {label}
      </dt>
      <dd className={`mt-1 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}
