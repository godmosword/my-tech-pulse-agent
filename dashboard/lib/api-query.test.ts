import { describe, expect, it } from "vitest";

import { startOfTodayTaipeiUtc } from "./api-query";

function expectedTaipeiMidnightUtc(): Date {
  const todayTpe = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Taipei",
  });
  return new Date(`${todayTpe}T00:00:00+08:00`);
}

describe("startOfTodayTaipeiUtc", () => {
  it("matches Asia/Taipei midnight encoded as +08:00", () => {
    const boundary = startOfTodayTaipeiUtc();
    expect(boundary.getTime()).toBe(expectedTaipeiMidnightUtc().getTime());
  });

  it("is stable within the same Taipei calendar day", () => {
    const a = startOfTodayTaipeiUtc();
    const b = startOfTodayTaipeiUtc();
    expect(a.getTime()).toBe(b.getTime());
  });
});
