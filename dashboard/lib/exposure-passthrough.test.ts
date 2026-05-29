import { describe, expect, it } from "vitest";

import { exposurePassthrough } from "./exposure-passthrough";
import type { CompanyRelationships } from "./relationship-data";

describe("exposurePassthrough", () => {
  it("flags double exposure when supplier is also held", () => {
    const nvdaRel: CompanyRelationships = {
      ticker: "NVDA",
      edges: [
        {
          counterparty_name: "Taiwan Semiconductor",
          counterparty_ticker: "TSM",
          relation: "supplier",
          quote: "verified quote text",
          verified: true,
        },
      ],
    };
    const out = exposurePassthrough(
      [{ ticker: "NVDA" }, { ticker: "TSM" }],
      { NVDA: nvdaRel },
      null,
      new Set(["TSM", "NVDA"]),
    );
    expect(out.some((e) => e.kind === "supply_chain" && e.severity === "warn")).toBe(
      true,
    );
    expect(out[0]?.message_zh).toContain("TSM");
    expect(out[0]?.message_zh).toContain("雙重曝險");
  });
});
