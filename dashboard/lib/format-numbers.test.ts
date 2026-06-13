import { describe, expect, it } from "vitest";

import { fmtNum, fmtPctPlain, fmtPctSigned, fmtUsd } from "./format-numbers";

const DASH = "—";

describe("fmtNum", () => {
  it("formats finite numbers with default 2 decimals", () => {
    expect(fmtNum(1.234)).toBe("1.23");
    expect(fmtNum(0)).toBe("0.00");
  });
  it("returns dash for nullish / non-finite", () => {
    expect(fmtNum(null)).toBe(DASH);
    expect(fmtNum(undefined)).toBe(DASH);
    expect(fmtNum(Number.NaN)).toBe(DASH);
    expect(fmtNum(Number.POSITIVE_INFINITY)).toBe(DASH);
  });
});

describe("fmtPctPlain", () => {
  it("formats without sign at 1 decimal", () => {
    expect(fmtPctPlain(12.34)).toBe("12.3%");
    expect(fmtPctPlain(-1.2)).toBe("-1.2%");
  });
  it("returns dash for nullish / non-finite", () => {
    expect(fmtPctPlain(null)).toBe(DASH);
    expect(fmtPctPlain(Number.NaN)).toBe(DASH);
  });
});

describe("fmtPctSigned", () => {
  it("prefixes a plus sign for positive values", () => {
    expect(fmtPctSigned(1.234)).toBe("+1.23%");
  });
  it("keeps zero unsigned", () => {
    expect(fmtPctSigned(0)).toBe("0.00%");
  });
  it("keeps negatives as-is", () => {
    expect(fmtPctSigned(-1.2)).toBe("-1.20%");
  });
  it("returns dash for nullish / non-finite (incl. Infinity)", () => {
    expect(fmtPctSigned(null)).toBe(DASH);
    expect(fmtPctSigned(undefined)).toBe(DASH);
    expect(fmtPctSigned(Number.NaN)).toBe(DASH);
    expect(fmtPctSigned(Number.POSITIVE_INFINITY)).toBe(DASH);
  });
});

describe("fmtUsd", () => {
  it("abbreviates billions", () => {
    expect(fmtUsd(2_500_000_000)).toBe("$2.50B");
    expect(fmtUsd(1e9)).toBe("$1.00B");
  });
  it("abbreviates millions", () => {
    expect(fmtUsd(1_500_000)).toBe("$1.50M");
    expect(fmtUsd(1e6)).toBe("$1.00M");
  });
  it("formats sub-million values with a $ prefix and no decimals", () => {
    // Locale-independent: derive the expected grouped integer the same way.
    const expected = `$${(123_456).toLocaleString(undefined, {
      maximumFractionDigits: 0,
    })}`;
    expect(fmtUsd(123_456)).toBe(expected);
  });
});
