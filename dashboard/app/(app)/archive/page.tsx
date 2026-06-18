import type { Metadata } from "next";
import { listLatestItems } from "@/lib/firestore";
import { categoryLabel } from "@/lib/digest";
import {
  buildArchiveHref,
  monthLabel,
  parseFilterState,
} from "@/lib/archive-filters";
import { listFilteredItemsLegacy } from "@/lib/items-list-page";
import { ArchiveList } from "@/components/archive/ArchiveList";
import {
  archiveItemFromRenderable,
  toInitialArchiveBuckets,
} from "@/lib/archive-list";
import { BackLink } from "@/components/BackLink";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
import { ClearFiltersLink } from "@/components/ClearFiltersLink";

/** Build 階段無 Firestore 憑證時避免 prerender 失敗。 */
export const dynamic = "force-dynamic";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "歸檔",
  description:
    "依 delivered_at 排序的科技脈搏專欄歸檔（標題公開；完整內文可登入閱讀）。",
};

const ARCHIVE_WINDOW_DAYS = 90;
const ARCHIVE_PAGE_SIZE = 40;

export default async function ArchivePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const state = parseFilterState(await searchParams);
  const since = new Date(Date.now() - ARCHIVE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const page = await listFilteredItemsLegacy(
    {
      limit: ARCHIVE_PAGE_SIZE,
      since,
      filters: state,
      kind: null,
      cursor: null,
    },
    listLatestItems,
  );
  const archiveItems = page.items.map(archiveItemFromRenderable);
  const buckets = toInitialArchiveBuckets(archiveItems);
  const filterKey = [state.category, state.month, state.ticker, since.toISOString()].join(
    "|",
  );

  return (
    <div className="pt-2">
      <BackLink href="/" label="返回 Today" />
      <header className="mt-4 space-y-4">
        <Kicker>Archive · Last {ARCHIVE_WINDOW_DAYS} days</Kicker>
        <h1 className="font-serif text-editorial-title text-ink">
          Today’s Paper, day by day.
        </h1>
        <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
          Sorted by delivered_at · most recent first
        </p>
        <Hairline />
        <ActiveFilters state={state} />
      </header>

      <div className="mt-10">
        <ArchiveList
          key={filterKey}
          initialBuckets={buckets}
          initialNextCursor={page.nextCursor}
          pageSize={ARCHIVE_PAGE_SIZE}
          sinceIso={since.toISOString()}
          filters={state}
          emptyMessage={
            archiveItems.length === 0 && !state.category && !state.month && !state.ticker
              ? "No items yet."
              : "目前篩選沒有符合的文章。"
          }
        />
      </div>
    </div>
  );
}

function ActiveFilters({
  state,
}: {
  state: ReturnType<typeof parseFilterState>;
}) {
  if (!state.category && !state.month && !state.ticker) return null;
  return (
    <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
      <span>篩選中：</span>
      {state.category && (
        <span className="ml-2 text-ink">{categoryLabel(state.category)}</span>
      )}
      {state.month && (
        <span className="ml-2 text-ink">{monthLabel(state.month)}</span>
      )}
      {state.ticker && (
        <span className="ml-2 font-mono text-ink">{state.ticker}</span>
      )}
      <ClearFiltersLink
        href={buildArchiveHref(state, {
          category: null,
          month: null,
          ticker: null,
        })}
        className="ml-3 text-ink-faint hover:text-accent"
      >
        清除
      </ClearFiltersLink>
    </p>
  );
}
