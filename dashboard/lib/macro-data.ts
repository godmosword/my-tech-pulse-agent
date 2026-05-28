import fs from "node:fs";
import path from "node:path";

export type MacroMetric = {
  value?: number;
  date?: string;
  trend?: string;
  unit?: string;
};

export type MacroContextSnapshot = {
  as_of?: string;
  macro?: Record<string, MacroMetric>;
  supply_chain?: {
    tsm?: {
      latest_month?: string;
      yoy_pct?: number | null;
      mom_pct?: number | null;
      trend?: string;
      source?: string;
    };
    sia?: {
      latest_month?: string;
      yoy_pct?: number | null;
      sales_usd_b?: number;
      trend?: string;
      source?: string;
      as_of?: string;
    };
    asml?: {
      quarter?: string;
      bookings_eur_b?: number;
      trend?: string;
      source?: string;
      as_of?: string;
      note?: string;
    };
  };
  theme_bias?: Record<
    string,
    { bias: "順風" | "中性" | "逆風"; drivers_zh: string[] }
  >;
};

function repoRootFromDashboard(): string {
  return path.resolve(process.cwd(), "..");
}

export function loadMacroContextSnapshot(): MacroContextSnapshot | null {
  const p = path.join(repoRootFromDashboard(), "output", "macro_context_latest.json");
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as MacroContextSnapshot;
  } catch {
    return null;
  }
}

export const THEME_LABELS: Record<string, string> = {
  ai_silicon: "AI 半導體",
  memory: "記憶體",
  equipment: "設備",
  semiconductor: "半導體",
  cloud_software: "雲端軟體",
  hardware: "硬體",
  optical: "光通訊",
  consumer_devices: "消費裝置",
};
