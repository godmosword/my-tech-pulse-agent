import { ArchiveSidebar } from "@/components/ArchiveSidebar";
import { listLatestItems } from "@/lib/firestore";
import { buildFacets, parseFilterState } from "@/lib/archive-filters";

/**
 * Right-rail for the home (today) route. Uses the same facet UI as /archive
 * — clicking a category or month navigates into /archive with that filter
 * applied, since "today" itself has no internal filter state.
 */
export const dynamic = "force-dynamic";
export const revalidate = 300;

export default async function HomeRail({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const state = parseFilterState(await searchParams);
  const items = await listLatestItems({ limit: 400 });
  const facets = buildFacets(items);
  return <ArchiveSidebar facets={facets} state={state} />;
}
