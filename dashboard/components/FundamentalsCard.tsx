import { fmtNum, fmtPctPlain } from "@/lib/format-numbers";

interface ValuationRatiosView {
  gross_margin?: number | null;
  operating_margin?: number | null;
  net_margin?: number | null;
  roe?: number | null;
  roic?: number | null;
  debt_to_equity?: number | null;
  fcf_margin?: number | null;
  source?: string;
  period_matched?: string;
}

interface SurprisePointView {
  period: string;
  eps_actual?: number | null;
  eps_estimate?: number | null;
  surprise_pct?: number | null;
}

interface FinancialHealthView {
  fcf?: number | null;
  fcf_conversion_pct?: number | null;
  roic_trend?: string;
  shareholder_returns_zh?: string;
  source_conflicts?: string[];
}

type Props = {
  ratios?: ValuationRatiosView | null;
  surpriseHistory?: SurprisePointView[];
  financialHealth?: FinancialHealthView | null;
};

export function FundamentalsCard({ ratios, surpriseHistory, financialHealth }: Props) {
  if (!ratios && !(surpriseHistory?.length) && !financialHealth?.source_conflicts?.length) {
    return null;
  }

  const approx = ratios?.period_matched === "approx";

  return (
    <>
      {ratios && (
        <section className="mt-10 rounded-lg border border-rule p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
              估值比率
            </h2>
            <span className="font-sans text-meta text-ink-faint">來源 {ratios.source ?? "fmp"}</span>
            {approx && (
              <span className="rounded border border-amber-500/40 px-2 py-0.5 font-sans text-meta text-amber-700 dark:text-amber-300">
                近似對齊
              </span>
            )}
          </div>
          <dl className="mt-4 grid gap-3 font-mono text-meta text-ink-soft sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-ink-faint">毛利率</dt>
              <dd>{fmtPctPlain(ratios.gross_margin)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">營益率</dt>
              <dd>{fmtPctPlain(ratios.operating_margin)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">淨利率</dt>
              <dd>{fmtPctPlain(ratios.net_margin)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">ROE</dt>
              <dd>{fmtPctPlain(ratios.roe)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">ROIC</dt>
              <dd>{fmtPctPlain(ratios.roic)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">負債比</dt>
              <dd>{fmtNum(ratios.debt_to_equity)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">FCF margin</dt>
              <dd>{fmtPctPlain(ratios.fcf_margin)}</dd>
            </div>
          </dl>
        </section>
      )}

      {surpriseHistory && surpriseHistory.length > 0 && (
        <section className="mt-6 rounded-lg border border-rule p-5">
          <h2
            id="eps-surprise-history-heading"
            className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
          >
            EPS Surprise 歷史
          </h2>
          <div className="mt-4 overflow-x-auto">
            <table
              className="w-full min-w-[320px] font-mono text-meta text-ink-soft"
              aria-labelledby="eps-surprise-history-heading"
            >
              <thead>
                <tr className="border-b border-rule text-left text-ink-faint">
                  <th scope="col" className="pb-2 pr-4 font-sans font-normal">期間</th>
                  <th scope="col" className="pb-2 pr-4 font-sans font-normal">Actual</th>
                  <th scope="col" className="pb-2 pr-4 font-sans font-normal">Est.</th>
                  <th scope="col" className="pb-2 font-sans font-normal">Surprise</th>
                </tr>
              </thead>
              <tbody>
                {surpriseHistory.slice(0, 8).map((row) => (
                  <tr key={row.period} className="border-b border-rule/60">
                    <td className="py-2 pr-4">{row.period}</td>
                    <td className="py-2 pr-4">{fmtNum(row.eps_actual)}</td>
                    <td className="py-2 pr-4">{fmtNum(row.eps_estimate)}</td>
                    <td className="py-2">{fmtPctPlain(row.surprise_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {financialHealth?.source_conflicts && financialHealth.source_conflicts.length > 0 && (
        <p className="mt-4 font-sans text-meta text-amber-700 dark:text-amber-400">
          SEC 與 FMP 現金流數據不一致：{financialHealth.source_conflicts.join(" · ")}
        </p>
      )}
    </>
  );
}
