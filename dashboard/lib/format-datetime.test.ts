import { describe, expect, it } from "vitest";

import {
  dayKeyTaipei,
  formatDashboardDate,
  formatDashboardDateTime,
  formatDashboardMetaDateTime,
  parseDashboardInstant,
} from "./format-datetime";

describe("format-datetime", () => {
  it("parses day keys at Taipei noon to avoid UTC drift", () => {
    const d = parseDashboardInstant("2026-05-18");
    expect(d).not.toBeNull();
    expect(dayKeyTaipei(d!)).toBe("2026-05-18");
    expect(formatDashboardDate("2026-05-18")).toContain("2026");
    expect(formatDashboardDate("2026-05-18")).toContain("18");
  });

  it("formats UTC instant on Taipei calendar boundary", () => {
    // 2026-05-17 20:00 UTC = 2026-05-18 04:00 Taipei
    const iso = "2026-05-17T20:00:00.000Z";
    expect(dayKeyTaipei(new Date(iso))).toBe("2026-05-18");
    expect(formatDashboardDate(iso)).toContain("18");
    expect(formatDashboardDateTime(iso)).toMatch(/18/);
  });

  it("returns empty string for missing values", () => {
    expect(formatDashboardDate(null)).toBe("");
    expect(formatDashboardDateTime("")).toBe("");
    expect(formatDashboardMetaDateTime(undefined)).toBe("");
  });

  it("formats compact meta datetime in zh-TW", () => {
    const out = formatDashboardMetaDateTime("2026-05-18T10:30:00.000Z");
    expect(out).toContain("·");
    expect(out).toMatch(/\d/);
  });
});
