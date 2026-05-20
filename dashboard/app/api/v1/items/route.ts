import { listLatestItems } from "@/lib/firestore";
import { filterListedItems, parseItemListQuery } from "@/lib/api-query";
import { serializeItem } from "@/lib/api-serialize";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (request, { access }) => {
  const query = parseItemListQuery(request);
  const fetchLimit = Math.min(query.limit * 4, 400);
  const items = await listLatestItems({
    limit: fetchLimit,
    since: query.since ?? undefined,
  });
  const filtered = filterListedItems(items, query);
  return apiJson({
    items: filtered.map((item) => serializeItem(item, access)),
    count: filtered.length,
    limit: query.limit,
  });
});
