import type {
  EvidenceLevel,
  TrackBucket,
  TrackRecord,
} from "@/lib/backtest-data";

const EVIDENCE_META: Record<
  EvidenceLevel,
  { label: string; className: string }
> = {
  insufficient: { label: "證據不足", className: "text-ink-faint" },
  weak: { label: "證據薄弱", className: "text-warn" },
  moderate: { label: "證據中等", className: "text-info" },
  strong: { label: "證據充分", className: "text-pos" },
};

function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function ci(range: [number, number] | null | undefined): string {
  if (!range) return "—";
  return `[${(range[0] * 100).toFixed(1)}%, ${(range[1] * 100).toFixed(1)}%]`;
}

function EvidenceBadge({ level }: { level: EvidenceLevel }) {
  const meta = EVIDENCE_META[level] ?? EVIDENCE_META.insufficient;
  return (
    <span className={`font-sans text-meta font-semibold ${meta.className}`}>
      {meta.label}
    </span>
  );
}

function BucketRow({ horizon, bucket }: { horizon: string; bucket: TrackBucket | null }) {
  if (!bucket) {
    return (
      <tr>
        <th scope="row" className="py-1 pr-3 text-left font-sans text-meta text-ink-soft">
          {horizon}日
        </th>
        <td colSpan={5} className="py-1 font-sans text-meta text-ink-faint">
          尚無成熟樣本
        </td>
      </tr>
    );
  }
  return (
    <tr>
      <th scope="row" className="py-1 pr-3 text-left font-sans text-meta text-ink-soft">
        {horizon}日
      </th>
      <td className="py-1 pr-3 font-mono text-meta text-ink">
        {pct(bucket.hit_rate)}{" "}
        <span className="text-ink-faint">{ci(bucket.hit_rate_ci)}</span>
      </td>
      <td className="py-1 pr-3 font-mono text-meta text-ink">
        {pct(bucket.mean_excess_pct)}{" "}
        <span className="text-ink-faint">{ci(bucket.mean_excess_ci)}</span>
      </td>
      <td className="py-1 pr-3 font-mono text-meta text-ink">
        {bucket.n}
        <span className="text-ink-faint"> / {bucket.n_effective}</span>
      </td>
      <td className="py-1 pr-3">
        <EvidenceBadge level={bucket.evidence_level} />
      </td>
    </tr>
  );
}

export function TrackRecordPanel({ data }: { data: TrackRecord }) {
  const tr = data.track_record;
  const byHorizon = tr?.by_horizon ?? {};
  const horizons = tr?.horizons ?? Object.keys(byHorizon).map(Number);
  const survivorship = data.survivorship;
  const maturity = data.maturity_breakdown ?? {};

  return (
    <section className="section-band mt-8">
      <header className="mb-2">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          訊號戰績（evidence governance · {data.signal_version ?? "—"}）
        </h2>
        <p className="mt-1 font-sans text-meta text-ink-faint">
          已評估 {data.n_evaluated ?? 0} / 紀錄 {data.n_logged ?? 0}（截至 {data.as_of ?? "—"}）。
          證據等級與訊號 conviction 分離：此處衡量「是否實證有效」，非訊號完整度。
        </p>
      </header>

      <table className="w-full border-collapse">
        <caption className="sr-only">各 horizon 的命中率、超額報酬與證據等級</caption>
        <thead>
          <tr className="border-b border-rule">
            <th scope="col" className="py-1 pr-3 text-left font-sans text-meta text-ink-faint">
              Horizon
            </th>
            <th scope="col" className="py-1 pr-3 text-left font-sans text-meta text-ink-faint">
              命中率 (Wilson CI)
            </th>
            <th scope="col" className="py-1 pr-3 text-left font-sans text-meta text-ink-faint">
              平均超額 (bootstrap CI)
            </th>
            <th scope="col" className="py-1 pr-3 text-left font-sans text-meta text-ink-faint">
              n / 有效
            </th>
            <th scope="col" className="py-1 pr-3 text-left font-sans text-meta text-ink-faint">
              證據
            </th>
          </tr>
        </thead>
        <tbody>
          {horizons.map((h) => (
            <BucketRow
              key={h}
              horizon={String(h)}
              bucket={byHorizon[String(h)]?.overall ?? null}
            />
          ))}
        </tbody>
      </table>

      <dl className="mt-3 grid grid-cols-1 gap-1 font-sans text-meta text-ink-soft sm:grid-cols-2">
        {survivorship && (
          <div>
            <dt className="inline text-ink-faint">Survivorship 覆蓋：</dt>{" "}
            <dd className="inline">
              {survivorship.covered}/{survivorship.total}
              {survivorship.biased && (
                <span className="text-warn">（偏誤風險，偏樂觀）</span>
              )}
            </dd>
          </div>
        )}
        <div>
          <dt className="inline text-ink-faint">成熟度：</dt>{" "}
          <dd className="inline">
            未成熟 {maturity.immature ?? 0}、缺價格 {maturity.missing_prices ?? 0}、
            無決策日 {maturity.no_decision_date ?? 0}
          </dd>
        </div>
      </dl>

      {tr?.multiple_comparisons?.note && (
        <p className="mt-2 font-sans text-meta text-ink-faint">
          多重比較：檢定 {tr.multiple_comparisons.buckets_tested} 個 bucket。
          {tr.multiple_comparisons.note}
        </p>
      )}
      {tr?.disclaimer_zh && (
        <p className="mt-1 font-sans text-meta text-ink-faint">{tr.disclaimer_zh}</p>
      )}
    </section>
  );
}
