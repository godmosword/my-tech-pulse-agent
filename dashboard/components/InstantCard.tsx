import Link from "next/link";
import { formatRelativeDate, formatScore } from "@/lib/digest";
import type { RenderableItem } from "@/lib/types";
import { ConfidenceBadge } from "./ConfidenceBadge";

export function InstantCard({ item }: { item: RenderableItem }) {
  const isEarnings = item.kind === "earnings";
  const prefix = isEarnings ? "📊" : "⭐";
  return (
    <article className="rounded-lg border border-slate-200/60 bg-surface-alt p-4 shadow-sm dark:border-slate-700/40 dark:bg-slate-900/40">
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <span className="font-mono">
          {prefix} {formatScore(item.score)}
        </span>
        <span aria-hidden>·</span>
        <ConfidenceBadge item={item} />
      </div>

      <h3 className="mt-2 text-base font-semibold leading-snug">
        <Link
          href={`/item/${encodeURIComponent(item.id)}`}
          className="hover:underline"
        >
          {item.title || item.entity || "Untitled"}
        </Link>
      </h3>

      {item.summary && (
        <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-muted">
          {item.summary}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-subtle">
        {item.published_at_iso && (
          <span>🕒 {formatRelativeDate(item.published_at_iso)}</span>
        )}
        {item.category && item.category !== "other" && (
          <span className="font-mono">#{item.category}</span>
        )}
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-ink-muted underline-offset-2 hover:underline"
          >
            🔗 {item.source_name || "原文連結"}
          </a>
        )}
      </div>
    </article>
  );
}
