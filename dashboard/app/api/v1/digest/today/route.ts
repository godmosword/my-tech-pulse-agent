import { serializeDigest } from "@/lib/api-serialize";
import { resolveDigestView } from "@/lib/digest-snapshot";
import {
  latestDeliveredIso,
  loadTodayDigestData,
} from "@/lib/today-digest";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (_request, { access }) => {
  const { items, snapshots, usingStaleFallback } = await loadTodayDigestData();
  const view = resolveDigestView(items, snapshots);
  const latestDelivered = latestDeliveredIso(items);

  return apiJson({
    timezone: "Asia/Taipei",
    latest_delivered_at: latestDelivered,
    stale_fallback: usingStaleFallback,
    digest: serializeDigest(view, access),
  });
});
