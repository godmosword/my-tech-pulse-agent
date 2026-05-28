import { BacktestCalibrationPanel } from "@/components/BacktestCalibrationPanel";
import { BackfillCode, BackfillHint } from "@/components/data/BackfillHint";
import { DensePageShell } from "@/components/data/DensePageShell";
import { hasInsufficientSample, loadBacktestSummary, loadLiveEvalSummary } from "@/lib/backtest-data";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "訊號校驗",
  description: "Point-in-time 回測與 live decision log 校準。",
};

export default function CalibrationPage() {
  const backtest = loadBacktestSummary();
  const live = loadLiveEvalSummary();
  const warn = hasInsufficientSample(backtest) || hasInsufficientSample(live?.summary);

  return (
    <DensePageShell
      kicker="Calibration"
      title="訊號校驗"
      description="讀取離線回測 backtest/results/summary.json 與（若存在）live 前向評估。回測排除 market_confirmation，非投資建議。"
      source="backtest/results"
    >
      {warn && (
        <p className="section-band border-warn/40 font-sans text-body font-semibold text-warn">
          樣本不足，回測僅供參考，非未來績效保證。
        </p>
      )}

      {!backtest ? (
        <BackfillHint
          title="尚無回測結果"
          note="Vercel 預設不含 backtest/results/。本機 npm run dev 可讀；若要在線展示可 commit summary.json 到 repo（非 gitignore）。"
        >
          <p>快速 smoke（3 檔 ticker，仍會寫入 backtest/results/summary.json）：</p>
          <BackfillCode>{`export FINNHUB_API_KEY=your_key
export SEC_USER_AGENT="YourName your@email.com"
python scripts/backtest_signal.py --dry-run`}</BackfillCode>
          <p>完整 watchlist：</p>
          <BackfillCode>python scripts/backtest_signal.py --since 2022-01-01</BackfillCode>
          <p>產物：summary.json、records.csv、report.md</p>
        </BackfillHint>
      ) : (
        <BacktestCalibrationPanel summary={backtest} title="離線回測（point-in-time）" />
      )}

      {live?.summary && (
        <BacktestCalibrationPanel
          summary={live.summary}
          title={`Live 前向校驗（n=${live.n_evaluated ?? 0} / 紀錄 ${live.n_logged ?? 0}）`}
        />
      )}
    </DensePageShell>
  );
}
