"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { LoadMoreButton } from "@/components/LoadMoreButton";
import { Hairline } from "@/components/Hairline";
import { Kicker, MetaDot } from "@/components/Kicker";
import { formatEditorialDate } from "@/lib/digest";
import type { FilterState } from "@/lib/archive-filters";
import {
  archiveItemFromApi,
  archiveKickerSegments,
  bucketArchiveByDay,
  mergeArchiveBuckets,
  type ArchiveDayBucket,
  type ArchiveListItem,
} from "@/lib/archive-list";
import type { ApiItem } from "@/lib/api-serialize";

type Props = {
  initialBuckets: ArchiveDayBucket[];
  initialNextCursor: string | null;
  pageSize: number;
  sinceIso: string;
  filters: FilterState;
  emptyMessage: string;
};

function buildArchiveApiUrl(
  filters: FilterState,
  sinceIso: string,
  pageSize: number,
  cursor?: string | null,
): string {
  const params = new URLSearchParams();
  params.set("limit", String(pageSize));
  params.set("since", sinceIso);
  if (filters.category) params.set("category", filters.category);
  if (filters.month) params.set("month", filters.month);
  if (filters.ticker) params.set("ticker", filters.ticker);
  if (cursor) params.set("cursor", cursor);
  return `/api/v1/items?${params.toString()}`;
}

export function ArchiveList({
  initialBuckets,
  initialNextCursor,
  pageSize,
  sinceIso,
  filters,
  emptyMessage,
}: Props) {
  const [buckets, setBuckets] = useState(initialBuckets);
  const [nextCursor, setNextCursor] = useState(initialNextCursor);

  const onLoadMore = useCallback(async () => {
    if (!nextCursor) return;
    const res = await fetch(buildArchiveApiUrl(filters, sinceIso, pageSize, nextCursor));
    if (!res.ok) {
      throw new Error("fetch failed");
    }
    const body = (await res.json()) as {
      items: ApiItem[];
      nextCursor: string | null;
    };
    const moreItems: ArchiveListItem[] = body.items.map(archiveItemFromApi);
    setBuckets((prev) => mergeArchiveBuckets(prev, moreItems));
    setNextCursor(body.nextCursor);
  }, [filters, nextCursor, pageSize, sinceIso]);

  if (buckets.length === 0) {
    return (
      <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
        {emptyMessage}
      </p>
    );
  }

  return (
    <>
      <div className="space-y-12">
        {buckets.map(({ dayIso, items: dayItems }) => (
          <section key={dayIso} className="space-y-4">
            <h2 className="font-serif text-[22px] leading-tight tracking-[-0.018em] text-ink sm:text-[26px]">
              {formatEditorialDate(dayIso) || "Undated"}
            </h2>
            <Hairline />
            <ul className="divide-y divide-rule">
              {dayItems.map((item) => {
                const kickerSegments = archiveKickerSegments(item);
                return (
                  <li key={item.id} className="py-4">
                    <Link
                      href={`/item/${encodeURIComponent(item.id)}`}
                      className="block space-y-2 hover:[&_h3]:underline"
                    >
                      {kickerSegments.length > 0 && (
                        <Kicker
                          as="div"
                          className="flex flex-wrap items-center text-ink-soft"
                        >
                          {kickerSegments.map((segment, index) => (
                            <span key={`${segment}-${index}`} className="contents">
                              {index > 0 && <MetaDot />}
                              <span>{segment}</span>
                            </span>
                          ))}
                        </Kicker>
                      )}
                      <h3 className="font-serif text-[17px] leading-snug text-ink sm:text-[19px]">
                        {item.title}
                      </h3>
                      {item.subline && (
                        <p className="font-sans text-[15px] leading-snug text-ink-soft">
                          {item.subline}
                        </p>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      <LoadMoreButton hasMore={Boolean(nextCursor)} onLoadMore={onLoadMore} />
    </>
  );
}

export function toInitialArchiveBuckets(
  items: ArchiveListItem[],
): ArchiveDayBucket[] {
  return bucketArchiveByDay(items);
}
