import { collectionName, listLatestItems } from "@/lib/firestore";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async () => {
  const items = await listLatestItems({ limit: 1 });
  const latest = items[0]?.delivered_at_iso ?? null;
  return apiJson({
    status: "ok",
    collection: collectionName(),
    latest_delivered_at: latest,
    item_count_sampled: items.length,
  });
});
