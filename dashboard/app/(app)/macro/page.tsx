import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
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
    <div>
      <Kicker tone="accent">Macro & Supply Chain</Kicker>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-ink">宏觀與供應鏈對照</h1>
      <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">
        慢資料加快取；manual 來源會標示 as_of。僅供環境參考，非投資建議。
      </p>

      <Hairline className="mt-6" />

      {!snapshot ? (
        <p className="mt-8 font-sans text-body text-ink-faint">
          尚無 macro_context。pipeline 合成 digest 後會寫入{" "}
          <code className="text-meta">output/macro_context_latest.json</code>，或本地執行
          pipeline 一次。
        </p>
      ) : (
        <MacroDashboardPanel
          snapshot={snapshot}
          portfolioEnv={portfolioEnv}
          weightedBias={weighted}
        />
      )}
    </div>
  );
}
