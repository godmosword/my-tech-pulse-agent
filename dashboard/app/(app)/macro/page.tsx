import { BackfillCode, BackfillHint } from "@/components/data/BackfillHint";
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
      breadcrumb={[
        { label: "投資", href: "/invest" },
        { label: "宏觀" },
      ]}
    >
      {!snapshot ? (
        <BackfillHint
          title="尚無 macro_context"
          note="Vercel 不會帶 output/（gitignore）。要在線上看到資料，需改讀 Firestore／API，或 commit 快照到 repo 並調整讀取路徑。本機 npm run dev 可直接讀 output/。"
        >
          <p>在 repo 根目錄產生 output/macro_context_latest.json（可選 FRED_API_KEY）：</p>
          <BackfillCode>{`python -c "
from agents.macro_context_builder import fetch_macro_context
import json
from pathlib import Path
ctx = fetch_macro_context()
Path('output').mkdir(exist_ok=True)
Path('output/macro_context_latest.json').write_text(
    json.dumps(ctx, ensure_ascii=False, indent=2), encoding='utf-8')
print('themes', len(ctx.get('theme_bias', {})))
"`}</BackfillCode>
          <p>或跑完整 pipeline（Stage 3 合成 digest 前會寫入同檔）：</p>
          <BackfillCode>python main.py</BackfillCode>
        </BackfillHint>
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
