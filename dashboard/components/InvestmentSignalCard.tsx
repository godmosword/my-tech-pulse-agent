import type {
  InvestmentSignalRow,
  SignalFactorRow,
} from "@/lib/earnings-firestore";

const FACTOR_LABELS: Record<string, string> = {
  fundamental_momentum: "基本面動能",
  surprise: "財報驚喜",
  market_confirmation: "市場確認",
  quality: "財務品質",
};

const RATING_STYLES: Record<string, string> = {
  強力看多: "border-emerald-600/50 bg-emerald-600/15 text-emerald-800 dark:text-emerald-300",
  看多: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  中性: "border-rule bg-paper text-ink-soft",
  看空: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  強力看空: "border-rose-600/50 bg-rose-600/15 text-rose-800 dark:text-rose-300",
  資料不足: "border-rule bg-paper text-ink-faint",
};

const CONVICTION_LABELS: Record<string, string> = {
  high: "高信心",
  medium: "中信心",
  low: "低信心",
};

type Props = {
  signal: InvestmentSignalRow;
};

function barColor(score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return "bg-ink-faint/30";
  if (score >= 60) return "bg-emerald-500/70";
  if (score <= 40) return "bg-rose-500/70";
  return "bg-amber-500/60";
}

function FactorBar({ factor }: { factor: SignalFactorRow }) {
  const label = FACTOR_LABELS[factor.name] ?? factor.name;
  if (!factor.available || factor.score == null) {
    return (
      <div>
        <div className="mb-1 flex justify-between font-sans text-meta text-ink-faint">
          <span>{label}</span>
          <span>資料不足</span>
        </div>
        <div className="h-2 rounded-full bg-ink-faint/20" />
      </div>
    );
  }
  return (
    <div>
      <div className="mb-1 flex justify-between font-sans text-meta text-ink-soft">
        <span>{label}</span>
        <span className="font-mono">{factor.score.toFixed(0)}</span>
      </div>
      <div className="h-2 rounded-full bg-ink-faint/15">
        <div
          className={`h-2 rounded-full ${barColor(factor.score)}`}
          style={{ width: `${Math.max(0, Math.min(100, factor.score))}%` }}
        />
      </div>
      {factor.detail_zh && (
        <p className="mt-1 font-sans text-meta text-ink-faint">{factor.detail_zh}</p>
      )}
    </div>
  );
}

export function InvestmentSignalCard({ signal }: Props) {
  const ratingClass = RATING_STYLES[signal.rating] ?? RATING_STYLES["資料不足"];
  const factors = signal.factors ?? [];

  return (
    <section className="mt-10 rounded-lg border border-rule p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
            投資訊號
          </h2>
          <p className="mt-1 font-sans text-meta text-ink-faint">
            系統綜合訊號，非投資建議
            {signal.as_of ? ` · ${signal.as_of}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded border px-3 py-1 font-sans text-body font-semibold ${ratingClass}`}
          >
            {signal.rating}
          </span>
          <span className="rounded border border-rule px-2 py-0.5 font-sans text-meta text-ink-soft">
            {CONVICTION_LABELS[signal.conviction] ?? signal.conviction}
          </span>
        </div>
      </div>

      {signal.score != null && (
        <p className="mt-4 font-serif text-5xl font-semibold tabular-nums text-ink">
          {signal.score.toFixed(1)}
          <span className="ml-2 font-sans text-meta font-normal text-ink-faint">/ 100</span>
        </p>
      )}

      {factors.length > 0 && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {factors.map((f) => (
            <FactorBar key={f.name} factor={f} />
          ))}
        </div>
      )}

      {signal.rationale_zh && (
        <p className="mt-5 font-sans text-body leading-relaxed text-ink-soft">
          {signal.rationale_zh}
        </p>
      )}
    </section>
  );
}
