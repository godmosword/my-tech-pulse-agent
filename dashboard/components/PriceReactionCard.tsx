export interface PriceReactionView {
  earnings_date?: string | null;
  session?: string;
  ret_1d_pct?: number | null;
  ret_5d_pct?: number | null;
  excess_1d_pct?: number | null;
  excess_5d_pct?: number | null;
  bench_symbol?: string;
  reaction_label?: string;
  degraded?: boolean;
}

const LABEL_STYLES: Record<string, string> = {
  確認上漲: "border-emerald-600/40 bg-emerald-600/10 text-emerald-800 dark:text-emerald-300",
  利多不漲: "border-amber-600/40 bg-amber-600/10 text-amber-800 dark:text-amber-300",
  利空出盡: "border-sky-600/40 bg-sky-600/10 text-sky-800 dark:text-sky-300",
  確認下跌: "border-rose-600/40 bg-rose-600/10 text-rose-800 dark:text-rose-300",
  中性: "border-rule bg-paper text-ink-soft",
  資料不足: "border-rule bg-paper text-ink-faint",
};

function fmtPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

type Props = {
  reaction: PriceReactionView;
};

export function PriceReactionCard({ reaction }: Props) {
  const label = reaction.reaction_label ?? "資料不足";
  const labelClass = LABEL_STYLES[label] ?? LABEL_STYLES["資料不足"];
  const bench = reaction.bench_symbol ?? "SOXX";

  return (
    <section className="mt-10 rounded-lg border border-rule p-5">
      <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
        市場反應
      </h2>
      {reaction.degraded && (
        <p className="mt-2 font-sans text-meta text-amber-700 dark:text-amber-400">
          近似資料（candle 不完整或部分以 quote 估算）
        </p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span
          className={`rounded border px-3 py-1 font-sans text-body font-semibold ${labelClass}`}
        >
          {label}
        </span>
        {reaction.earnings_date && (
          <span className="font-mono text-meta text-ink-faint">
            財報日 {reaction.earnings_date} · {reaction.session ?? "unknown"}
          </span>
        )}
      </div>
      <dl className="mt-4 grid gap-3 font-mono text-meta text-ink-soft sm:grid-cols-2">
        <div>
          <dt className="text-ink-faint">1 日報酬</dt>
          <dd>{fmtPct(reaction.ret_1d_pct)}</dd>
        </div>
        <div>
          <dt className="text-ink-faint">5 日報酬</dt>
          <dd>{fmtPct(reaction.ret_5d_pct)}</dd>
        </div>
        <div>
          <dt className="text-ink-faint">超額 1 日 vs {bench}</dt>
          <dd>{fmtPct(reaction.excess_1d_pct)}</dd>
        </div>
        <div>
          <dt className="text-ink-faint">超額 5 日 vs {bench}</dt>
          <dd>{fmtPct(reaction.excess_5d_pct)}</dd>
        </div>
      </dl>
    </section>
  );
}
