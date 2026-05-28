import { DensePageShell } from "@/components/data/DensePageShell";
import { MacroDashboardPanel } from "@/components/MacroDashboardPanel";
import { loadMacroContextSnapshot } from "@/lib/macro-data";
import {
  portfolioEnvironment,
  weightedEnvironmentBias,
} from "@/lib/portfolio-metrics";
import { buildPortfolioPayload } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "宏觀與供應鏈",
  description: "FRED 宏觀、TSM/SIA 供應鏈與主題環境對照。",
};

export default async function MacroPage() {
  const snapshot = loadMacroContextSnapshot();
  let portfolioEnv;
  let weighted;

  try {
    const payload = await buildPortfolioPayload();
    if (snapshot?.theme_bias && payload.theme_exposure.length) {
      portfolioEnv = portfolioEnvironment(payload.theme_exposure, snapshot.theme_bias);
      weighted = weightedEnvironmentBias(portfolioEnv);
    }
  } catch {
    portfolioEnv = undefined;
  }

  return (
    <DensePageShell
      kicker="Macro & Supply Chain"
      title="宏觀與供應鏈對照"
      description="慢資料加快取；manual 來源會標示 as_of。僅供環境參考，非投資建議。"
      source={snapshot ? "macro_context_latest.json" : undefined}
      asOf={snapshot?.as_of?.slice(0, 10)}
    >
      {!snapshot ? (
        <p className="font-sans text-body text-ink-faint">
          尚無 macro_context。pipeline 合成 digest 後會寫入 output/macro_context_latest.json，或本地執行
          pipeline 一次。
        </p>
      ) : (
        <MacroDashboardPanel
          snapshot={snapshot}
          portfolioEnv={portfolioEnv}
          weightedBias={weighted}
        />
      )}
    </DensePageShell>
  );
}
