import Link from "next/link";
import type { RenderableItem } from "@/lib/types";

/**
 * Renders a deep brief in the same three-part shape used by the Telegram
 * formatter: 【核心洞見】/【底層邏輯】/【生態影響】.
 *
 * The pipeline merges these three sections into `summary` separated by two
 * newlines (see scoring/memory_store.archive_deep_brief). We split on the
 * blank line; if the source didn't follow the contract, we render the full
 * blob as-is.
 */
export function DeepInsightCard({ item }: { item: RenderableItem }) {
  const parts = splitThreePart(item.summary);

  return (
    <article className="rounded-lg border border-indigo-200/60 bg-indigo-50/30 p-5 shadow-sm dark:border-indigo-800/40 dark:bg-indigo-900/15">
      <h3 className="text-base font-semibold leading-snug">
        🧠{" "}
        <Link
          href={`/item/${encodeURIComponent(item.id)}`}
          className="hover:underline"
        >
          {item.title || item.entity || "Untitled"}
        </Link>
      </h3>
      <p className="mt-1 text-xs text-ink-subtle">
        {item.source_name || "source"}
      </p>

      <dl className="mt-4 space-y-3 text-sm leading-relaxed">
        <Section label="核心洞見" body={parts.insight} />
        <Section label="底層邏輯" body={parts.tech_rationale} />
        <Section label="生態影響" body={parts.implication} />
      </dl>

      {item.source_url && (
        <div className="mt-4 text-sm">
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-indigo-700 hover:underline dark:text-indigo-300"
          >
            🔗 原文連結
          </a>
        </div>
      )}
    </article>
  );
}

function Section({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div>
      <dt className="text-xs font-semibold text-ink-muted">【{label}】</dt>
      <dd className="mt-1 whitespace-pre-line text-ink">{body}</dd>
    </div>
  );
}

function splitThreePart(summary: string): {
  insight: string;
  tech_rationale: string;
  implication: string;
} {
  const blocks = (summary || "")
    .split(/\n\s*\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (blocks.length >= 3) {
    return {
      insight: blocks[0]!,
      tech_rationale: blocks[1]!,
      implication: blocks.slice(2).join("\n\n"),
    };
  }
  return { insight: summary, tech_rationale: "", implication: "" };
}
