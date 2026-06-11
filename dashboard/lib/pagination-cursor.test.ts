import { describe, expect, it } from "vitest";

import {
  decodeEarningsCursor,
  decodeItemCursor,
  decodeSignalCursor,
  encodeEarningsCursor,
  encodeItemCursor,
  encodeSignalCursor,
} from "./pagination-cursor";

describe("pagination-cursor", () => {
  it("round-trips item cursor", () => {
    const raw = encodeItemCursor({
      deliveredAtIso: "2026-05-18T10:00:00.000Z",
      id: "item-1",
    });
    expect(decodeItemCursor(raw)).toEqual({
      deliveredAtIso: "2026-05-18T10:00:00.000Z",
      id: "item-1",
    });
  });

  it("round-trips earnings cursor", () => {
    const raw = encodeEarningsCursor({
      publishedAtIso: "2026-05-18T10:00:00.000Z",
      reportId: "r1",
    });
    expect(decodeEarningsCursor(raw)).toEqual({
      publishedAtIso: "2026-05-18T10:00:00.000Z",
      reportId: "r1",
    });
  });

  it("round-trips signal cursor", () => {
    const raw = encodeSignalCursor({ score: 72.5, reportId: "r9" });
    expect(decodeSignalCursor(raw)).toEqual({ score: 72.5, reportId: "r9" });
  });

  it("returns null for invalid cursor", () => {
    expect(decodeItemCursor("not-valid")).toBeNull();
    expect(decodeEarningsCursor("")).toBeNull();
    expect(decodeSignalCursor(undefined)).toBeNull();
  });
});
