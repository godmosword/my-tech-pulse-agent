import fs from "node:fs";
import path from "node:path";

export type RelationshipEdge = {
  counterparty_name: string;
  counterparty_ticker?: string | null;
  relation: "customer" | "supplier" | "competitor" | "partner";
  quote: string;
  concentration_note?: string;
  verified: boolean;
};

export type CompanyRelationships = {
  ticker: string;
  fiscal_year?: number | null;
  source_form?: string;
  filed?: string | null;
  edges: RelationshipEdge[];
  as_of?: string | null;
};

export type CorrelationCluster = {
  cluster_id: number;
  members: string[];
  avg_intra_corr: number;
};

export type ClustersSnapshot = {
  as_of?: string;
  window?: number;
  threshold?: number;
  tickers?: string[];
  skipped?: string[];
  clusters?: CorrelationCluster[];
  correlations?: Record<string, Array<{ ticker: string; corr: number }>>;
};

function repoRootFromDashboard(): string {
  return path.resolve(process.cwd(), "..");
}

export function loadCompanyRelationships(
  ticker: string,
): CompanyRelationships | null {
  const p = path.join(
    repoRootFromDashboard(),
    "data",
    "relationships",
    `${ticker.toUpperCase()}.json`,
  );
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as CompanyRelationships;
  } catch {
    return null;
  }
}

export function loadClustersSnapshot(): ClustersSnapshot | null {
  const p = path.join(repoRootFromDashboard(), "data", "clusters.json");
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as ClustersSnapshot;
  } catch {
    return null;
  }
}

export function marketContextForTicker(
  ticker: string,
  clusters: ClustersSnapshot | null,
): {
  correlated: Array<{ ticker: string; corr: number }>;
  cluster: CorrelationCluster | null;
} {
  const sym = ticker.toUpperCase();
  const correlated = clusters?.correlations?.[sym] ?? [];
  const cluster =
    clusters?.clusters?.find((c) => c.members.includes(sym)) ?? null;
  return { correlated, cluster };
}
