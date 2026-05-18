import { ArchiveSidebar } from "@/components/ArchiveSidebar";
import { listLatestItems } from "@/lib/firestore";
import {
  buildFacets,
  parseFilterState,
} from "@/lib/archive-filters";

/**
 * Right-rail counterpart for /archive. Same data window as the main page so
 * facet counts match what the user sees, but rendered as a sticky sidebar
 * on lg+ and stacked below the list on mobile (positioning done by the
 * parent (app)/layout grid).
 */
export const dynamic = "force-dynamic";
export const revalidate = 300;

const ARCHIVE_WINDOW_DAYS = 90;

export default async function ArchiveRail({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const state = parseFilterState(await searchParams);
  const since = new Date(Date.now() - ARCHIVE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const items = await listLatestItems({ limit: 400, since });
  const facets = buildFacets(items);
  return <ArchiveSidebar facets={facets} state={state} />;
}
