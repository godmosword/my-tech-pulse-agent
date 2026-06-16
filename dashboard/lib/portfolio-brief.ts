import type { RenderableItem } from "./types";

/**
 * Impact → non-transactional posture label.
 *
 * Mirrors the impact bands in scoring/posture.py (0.15 / 0.40). The full Python
 * posture also applies evidence-softening and a per-ticker cooldown, which need
 * cross-run state not available at read time; the dashboard shows the band-only
 * label and never escalates into a buy/sell.
 */
export type ImpactPosture = "no_action" | "monitor" | "review";

export const IMPACT_POSTURE_LABEL: Record<ImpactPosture, string> = {
  no_action: "無需動作",
  monitor: "需要注意",
  review: "需要複核",
};

export const IMPACT_POSTURE_CLASS: Record<ImpactPosture, string> = {
  no_action: "text-ink-faint",
  monitor: "text-info",
  review: "text-warn",
};

export function impactPosture(score: number): ImpactPosture {
  if (score < 0.15) return "no_action";
  if (score < 0.4) return "monitor";
  return "review";
}

export function impactScore(item: RenderableItem): number {
  return item.portfolio_impact?.score ?? 0;
}

/**
 * Guards against a foreign 0-10 writer polluting the shared portfolio_impact.score
 * field — only the deterministic 0-1 range is valid here (mirrors the Python
 * MAX_TRUSTED_IMPACT guard in scoring/invest_brief.py).
 */
export function isTrustedImpact(item: RenderableItem): boolean {
  const s = impactScore(item);
  return s > 0 && s <= 1;
}

/** Items that touch the book, strongest impact first. */
export function rankItemsByImpact(
  items: RenderableItem[],
  limit = 6,
): RenderableItem[] {
  return items
    .filter(isTrustedImpact)
    .sort((a, b) => impactScore(b) - impactScore(a))
    .slice(0, limit);
}
