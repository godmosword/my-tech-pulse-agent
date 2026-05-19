import {
  buildArchiveHref,
  type ArchiveFacets,
  type FilterState,
} from "@/lib/archive-filters";

import { ClearFiltersLink } from "./ClearFiltersLink";
import { Kicker } from "./Kicker";

interface Props {
  facets: ArchiveFacets;
  state: FilterState;
}

export function ArchiveSidebar({ facets, state }: Props) {
  return (
    <aside className="space-y-8 font-sans text-meta">
      <FilterGroup
        kicker="主題分類"
        emptyLabel="尚無分類資料"
        items={facets.categories}
        activeValue={state.category}
        buildHref={(value) => buildArchiveHref(state, { category: value })}
        clearHref={buildArchiveHref(state, { category: null })}
      />
      <FilterGroup
        kicker="月份"
        emptyLabel="尚無月份資料"
        items={facets.months}
        activeValue={state.month}
        buildHref={(value) => buildArchiveHref(state, { month: value })}
        clearHref={buildArchiveHref(state, { month: null })}
      />
    </aside>
  );
}

interface FilterGroupProps {
  kicker: string;
  emptyLabel: string;
  items: { value: string; label: string; count?: number }[];
  activeValue: string | null;
  buildHref: (value: string) => string;
  clearHref: string;
}

function FilterGroup({
  kicker,
  emptyLabel,
  items,
  activeValue,
  buildHref,
  clearHref,
}: FilterGroupProps) {
  return (
    <div className="space-y-3">
      <Kicker as="div">{kicker}</Kicker>
      {items.length === 0 ? (
        <p className="text-ink-faint">{emptyLabel}</p>
      ) : (
        <ul className="space-y-1.5">
          <li>
            <ClearFiltersLink
              href={clearHref}
              className={
                activeValue === null
                  ? "font-semibold text-ink"
                  : "text-ink-soft hover:text-accent"
              }
            >
              全部
            </ClearFiltersLink>
          </li>
          {items.map((it) => {
            const isActive = activeValue === it.value;
            return (
              <li key={it.value}>
                <ClearFiltersLink
                  href={buildHref(it.value)}
                  className={
                    "flex items-baseline justify-between gap-2 " +
                    (isActive
                      ? "font-semibold text-ink"
                      : "text-ink-soft hover:text-accent")
                  }
                >
                  <span className="truncate">{it.label}</span>
                  {it.count !== undefined && (
                    <span className="shrink-0 tabular-nums text-ink-faint">
                      {it.count}
                    </span>
                  )}
                </ClearFiltersLink>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
