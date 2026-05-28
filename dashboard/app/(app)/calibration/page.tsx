import { BacktestCalibrationPanel } from "@/components/BacktestCalibrationPanel";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
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
    <div>
      <Kicker tone="accent">Calibration</Kicker>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-ink">訊號校驗</h1>
      <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">
        讀取離線回測 <code className="text-meta">backtest/results/summary.json</code>{" "}
        與（若存在）live 前向評估。回測排除 market_confirmation，非投資建議。
      </p>

      {warn && (
        <p className="mt-4 font-sans text-body font-semibold text-rose-600 dark:text-rose-400">
          樣本不足，回測僅供參考，非未來績效保證。
        </p>
      )}

      <Hairline className="mt-6" />

      {!backtest ? (
        <p className="mt-8 font-sans text-body text-ink-faint">
          尚無回測結果。請在 repo 根目錄執行：{" "}
          <code className="text-meta">python scripts/backtest_signal.py --dry-run</code>
        </p>
      ) : (
        <BacktestCalibrationPanel summary={backtest} title="離線回測（point-in-time）" />
      )}

      {live?.summary && (
        <div className="mt-12">
          <BacktestCalibrationPanel
            summary={live.summary}
            title={`Live 前向校驗（n=${live.n_evaluated ?? 0} / 紀錄 ${live.n_logged ?? 0}）`}
          />
        </div>
      )}
    </div>
  );
}
