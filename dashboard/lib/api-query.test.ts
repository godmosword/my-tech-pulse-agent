import { describe, expect, it } from "vitest";

import { startOfTodayTaipeiUtc } from "./api-query";

describe("startOfTodayTaipeiUtc", () => {
  it("returns midnight Asia/Taipei as a UTC Date", () => {
    const boundary = startOfTodayTaipeiUtc();
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Taipei",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(boundary);

    const get = (type: string) =>
      parts.find((p) => p.type === type)?.value ?? "";

    expect(get("hour")).toBe("00");
    expect(get("minute")).toBe("00");
  });

  it("is stable within the same Taipei calendar day", () => {
    const a = startOfTodayTaipeiUtc();
    const b = startOfTodayTaipeiUtc();
    expect(a.getTime()).toBe(b.getTime());
  });
});
