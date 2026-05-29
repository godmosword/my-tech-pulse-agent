import type { CompanyRelationships, CorrelationCluster } from "./relationship-data";

export type PositionInput = { ticker: string };

export type IndirectExposure = {
  kind: "supply_chain" | "correlation_cluster";
  message_zh: string;
  tickers: string[];
  severity: "warn" | "info";
};

const SUPPLY_RELATIONS = new Set(["supplier", "customer"]);

function holdingSet(positions: PositionInput[]): Set<string> {
  return new Set(positions.map((p) => p.ticker.toUpperCase()));
}

/**
 * Flag indirect exposure when a holding's 10-K supplier/customer is also held,
 * or when multiple holdings share a high-correlation cluster.
 */
export function exposurePassthrough(
  positions: PositionInput[],
  relationshipsByTicker: Record<string, CompanyRelationships | null | undefined>,
  clusters: CorrelationCluster[] | null | undefined,
  watchlistTickers: Set<string>,
): IndirectExposure[] {
  const held = holdingSet(positions);
  const out: IndirectExposure[] = [];

  for (const pos of positions) {
    const sym = pos.ticker.toUpperCase();
    const rel = relationshipsByTicker[sym];
    if (!rel?.edges?.length) continue;

    for (const edge of rel.edges) {
      if (!SUPPLY_RELATIONS.has(edge.relation)) continue;
      const cp = edge.counterparty_ticker?.toUpperCase();
      if (!cp || cp === sym) continue;
      const inPortfolio = held.has(cp);
      const onWatchlist = watchlistTickers.has(cp);
      if (!inPortfolio && !onWatchlist) continue;

      const relationZh =
        edge.relation === "supplier" ? "供應商" : "客戶";
      const via = inPortfolio ? "直接持股" : "觀察清單";
      out.push({
        kind: "supply_chain",
        severity: inPortfolio ? "warn" : "info",
        tickers: [sym, cp],
        message_zh: `對 ${cp} 雙重曝險（${via} + 透過 ${sym} 的${relationZh} ${edge.counterparty_name}）`,
      });
    }
  }

  if (clusters?.length && held.size >= 2) {
    for (const cluster of clusters) {
      const overlap = cluster.members.filter((m) => held.has(m));
      if (overlap.length >= 2) {
        out.push({
          kind: "correlation_cluster",
          severity: "warn",
          tickers: overlap,
          message_zh: `持倉 ${overlap.join("、")} 落在同一相關性叢集（平均相關 ${(cluster.avg_intra_corr * 100).toFixed(0)}%），分散度偏低`,
        });
      }
    }
  }

  return out;
}
