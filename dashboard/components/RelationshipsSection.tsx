"use client";

import type { CompanyRelationships } from "@/lib/relationship-data";

type Props = {
  business: CompanyRelationships;
  correlated: Array<{ ticker: string; corr: number }>;
};

function RelationColumn({
  title,
  edges,
}: {
  title: string;
  edges: CompanyRelationships["edges"];
}) {
  if (!edges.length) {
    return (
      <div className="rounded border border-rule p-3">
        <h3 className="font-sans text-meta uppercase tracking-widest text-ink-faint">
          {title}
        </h3>
        <p className="mt-2 font-sans text-meta text-ink-faint">—</p>
      </div>
    );
  }
  return (
    <div className="rounded border border-rule p-3">
      <h3 className="font-sans text-meta uppercase tracking-widest text-ink-faint">
        {title}
      </h3>
      <ul className="mt-3 space-y-3">
        {edges.map((e, i) => (
          <li key={`${e.counterparty_name}-${i}`} className="group relative">
            <p className="font-sans text-body text-ink">
              {e.counterparty_name}
              {e.counterparty_ticker ? (
                <span className="text-ink-faint"> ({e.counterparty_ticker})</span>
              ) : null}
            </p>
            {e.concentration_note ? (
              <p className="mt-0.5 font-sans text-meta text-ink-soft">
                {e.concentration_note}
              </p>
            ) : null}
            <p
              className="mt-1 hidden font-sans text-meta text-ink-faint group-hover:block"
              title="10-K 原文出處"
            >
              {e.verified ? "✓ " : ""}
              {e.quote}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RelationshipsSection({ business, correlated }: Props) {
  const byRelation = (kind: string) =>
    business.edges.filter((e) => e.relation === kind);

  return (
    <section className="mt-10">
      <h2 className="font-sans text-meta uppercase tracking-widest text-ink-faint">
        關係（10-K）
      </h2>
      {business.filed ? (
        <p className="mt-1 font-sans text-meta text-ink-faint">
          申報 {business.filed}
          {business.fiscal_year ? ` · FY${business.fiscal_year}` : ""}
        </p>
      ) : null}

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <RelationColumn title="客戶" edges={byRelation("customer")} />
        <RelationColumn title="供應商" edges={byRelation("supplier")} />
        <RelationColumn title="競爭者" edges={byRelation("competitor")} />
      </div>

      {byRelation("partner").length > 0 && (
        <div className="mt-4">
          <RelationColumn title="夥伴" edges={byRelation("partner")} />
        </div>
      )}

      {correlated.length > 0 && (
        <div className="mt-6">
          <h3 className="font-sans text-meta uppercase tracking-widest text-ink-faint">
            市場同動股
          </h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {correlated.map((c) => (
              <li
                key={c.ticker}
                className="rounded border border-rule px-2 py-1 font-sans text-meta text-ink-soft"
              >
                {c.ticker}{" "}
                <span className="text-ink-faint">
                  {(c.corr * 100).toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
