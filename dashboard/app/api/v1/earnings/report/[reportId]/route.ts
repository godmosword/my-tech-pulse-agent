import { getEarningsReport } from "@/lib/earnings-firestore";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(
  async (_request, context: { params: Promise<{ reportId: string }> }) => {
    const { reportId } = await context.params;
    const row = await getEarningsReport(decodeURIComponent(reportId));
    if (!row) {
      return apiJson({ error: "not_found" }, { status: 404 });
    }
    return apiJson({ item: row });
  }
);
