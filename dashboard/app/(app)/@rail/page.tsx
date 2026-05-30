import { TodayRail } from "@/components/TodayRail";
import { loadTodayDigestData } from "@/lib/today-digest";

/**
 * Right-rail for the home (today) route. Shows today's snapshot: category
 * counts with colored dots, top mentioned tickers, and priority distribution.
 *
 * Uses the same Asia/Taipei "today" boundary and stale fallback as `(app)/page.tsx`.
 */
export const dynamic = "force-dynamic";
export const revalidate = 300;

export default async function HomeRail() {
  const { items, usingStaleFallback } = await loadTodayDigestData();
  return <TodayRail items={items} usingStaleFallback={usingStaleFallback} />;
}
