import { listLatestItems } from "@/lib/firestore";
import { buildDigest } from "@/lib/digest";
import { startOfTodayTaipeiUtc } from "@/lib/api-query";
import { serializeDigest } from "@/lib/api-serialize";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (_request, { access }) => {
  const todayStart = startOfTodayTaipeiUtc();
  let items = await listLatestItems({ limit: 80, since: todayStart });
  if (items.length === 0) {
    items = await listLatestItems({ limit: 80 });
  }
  const view = buildDigest(items);
  const latestDelivered = items
    .map((i) => i.delivered_at_iso)
    .filter((iso): iso is string => Boolean(iso))
    .sort()
    .reverse()[0] ?? null;

  return apiJson({
    timezone: "Asia/Taipei",
    latest_delivered_at: latestDelivered,
    digest: serializeDigest(view, access),
  });
});
