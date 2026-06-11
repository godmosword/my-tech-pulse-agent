import { listLatestItems } from "@/lib/firestore";
import { parseItemListQuery } from "@/lib/api-query";
import {
  listFilteredItemsLegacy,
  listFilteredItemsPage,
} from "@/lib/items-list-page";
import { serializeItem } from "@/lib/api-serialize";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (request, { access }) => {
  const query = parseItemListQuery(request);
  const page = query.cursor
    ? await listFilteredItemsPage(query, query.cursor)
    : await listFilteredItemsLegacy(query, listLatestItems);
  return apiJson({
    items: page.items.map((item) => serializeItem(item, access)),
    count: page.items.length,
    limit: query.limit,
    nextCursor: page.nextCursor,
  });
});
