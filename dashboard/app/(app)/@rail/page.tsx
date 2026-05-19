import { TodayRail } from "@/components/TodayRail";
import { listLatestItems } from "@/lib/firestore";

/**
 * Right-rail for the home (today) route. Shows today's snapshot: category
 * counts with colored dots, top mentioned tickers, and priority distribution.
 *
 * Uses the same Asia/Taipei "today" boundary as `(app)/page.tsx` so the
 * dashboard and the article list agree on what counts as today. Falls back
 * to the latest batch when today is empty so the rail is never blank.
 */
export const dynamic = "force-dynamic";
export const revalidate = 300;

export default async function HomeRail() {
  const todayStart = startOfTodayTaipeiUtc();
  let items = await listLatestItems({ limit: 80, since: todayStart });
  if (items.length === 0) {
    items = await listLatestItems({ limit: 80 });
  }
  return <TodayRail items={items} />;
}

/** Returns the UTC instant that corresponds to 00:00 today in Asia/Taipei. */
function startOfTodayTaipeiUtc(): Date {
  const todayTpe = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Taipei",
  });
  return new Date(`${todayTpe}T00:00:00+08:00`);
}
