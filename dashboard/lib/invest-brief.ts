import fs from "node:fs";
import path from "node:path";

export type BriefPosture = "no_action" | "monitor" | "review" | "risk_up";

export const POSTURE_CLASS: Record<BriefPosture, string> = {
  no_action: "text-ink-faint",
  monitor: "text-info",
  review: "text-warn",
  risk_up: "text-neg",
};

export type RiskFlag = {
  kind: string;
  severity: string;
  tickers: string[];
  message_zh: string;
};

export type Holding = { ticker: string; weight: number };

export type PortfolioPulse = {
  top_holdings: Holding[];
  concentration_top_pct: number;
  risk_flags: RiskFlag[];
};

export type BriefItem = {
  id: string;
  title: string;
  impact_score: number;
  posture: BriefPosture;
  label_zh: string;
  reason_zh: string;
  falsification_zh: string;
  next_check: string;
  affected_tickers: string[];
  market_flags: string[];
};

export type ThesisEvidence = {
  ticker: string;
  thesis: string;
  supporting: string[];
  contradicting: string[];
  upcoming: string[];
};

export type CatalystRow = {
  ticker: string;
  date: string;
  type: string;
  note?: string;
};

export type InvestBrief = {
  generated_at: string;
  evidence_level: string;
  portfolio_pulse: PortfolioPulse;
  material_items: BriefItem[];
  catalyst_watch: CatalystRow[];
  thesis_updates: ThesisEvidence[];
};

export function loadInvestBrief(): InvestBrief | null {
  const p = path.join(
    process.cwd(),
    "..",
    "backtest",
    "results",
    "invest_brief.json",
  );
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as InvestBrief;
  } catch {
    return null;
  }
}
