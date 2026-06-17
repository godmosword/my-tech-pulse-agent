import { POSTURE_CLASS, type BriefItem } from "@/lib/invest-brief";
import {
  IMPACT_POSTURE_CLASS,
  IMPACT_POSTURE_LABEL,
  impactPosture,
  impactScore,
} from "@/lib/portfolio-brief";
import { displayTitle, type RenderableItem } from "@/lib/types";

/**
 * Presentation view-model for a "material move" decision row. Both the
 * authoritative brief artifact (`BriefItem`, with cooldown/evidence-softened
 * posture) and the live fallback (`RenderableItem` + `portfolio_impact`) map
 * into this single shape so one row component renders both without forcing
 * either data contract to change.
 */
export interface MaterialMoveView {
  id: string;
  title: string;
  /** Link to the full item when an id is available. */
  href?: string;
  /** Tailwind text-color class for the posture label. */
  postureClass: string;
  postureLabel: string;
  reason: string;
  affectedTickers: string[];
  /** Only the brief artifact carries these; live fallback leaves them empty. */
  marketFlags: string[];
  falsification?: string;
  nextCheck?: string;
}

function itemHref(id: string): string | undefined {
  return id ? `/item/${encodeURIComponent(id)}` : undefined;
}

/** Map an authoritative brief item (carries posture + falsification + checks). */
export function materialMoveFromBrief(it: BriefItem): MaterialMoveView {
  return {
    id: it.id,
    title: it.title,
    href: itemHref(it.id),
    postureClass: POSTURE_CLASS[it.posture],
    postureLabel: it.label_zh,
    reason: it.reason_zh,
    affectedTickers: it.affected_tickers,
    marketFlags: it.market_flags,
    falsification: it.falsification_zh || undefined,
    nextCheck: it.next_check || undefined,
  };
}

/** Map a live item via its deterministic `portfolio_impact` (band-only posture). */
export function materialMoveFromItem(item: RenderableItem): MaterialMoveView {
  const posture = impactPosture(impactScore(item));
  const impact = item.portfolio_impact;
  return {
    id: item.id,
    title: displayTitle(item),
    href: itemHref(item.id),
    postureClass: IMPACT_POSTURE_CLASS[posture],
    postureLabel: IMPACT_POSTURE_LABEL[posture],
    reason: impact?.rationale_zh ?? "",
    affectedTickers: (impact?.affected_positions ?? []).map((a) => a.ticker),
    marketFlags: [],
  };
}
