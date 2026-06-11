import { describe, expect, it } from "vitest";

import {
  extractMarkdownHeadings,
  hasRenderableMarkdown,
  slugifyHeading,
} from "./earnings-report-markdown";

describe("extractMarkdownHeadings", () => {
  it("extracts h2 and h3 in order with stable ids", () => {
    const md = `## Scorecard\n\n### 營收\n\n## 結論`;
    const items = extractMarkdownHeadings(md);
    expect(items).toHaveLength(3);
    expect(items[0]).toMatchObject({ level: 2, text: "Scorecard" });
    expect(items[1]).toMatchObject({ level: 3, text: "營收" });
    expect(items[2]).toMatchObject({ level: 2, text: "結論" });
    expect(new Set(items.map((item) => item.id)).size).toBe(3);
  });
});

describe("slugifyHeading", () => {
  it("deduplicates identical headings", () => {
    const used = new Set<string>();
    const a = slugifyHeading("分部", used);
    const b = slugifyHeading("分部", used);
    expect(a).not.toBe(b);
  });
});

describe("hasRenderableMarkdown", () => {
  it("returns false for empty content", () => {
    expect(hasRenderableMarkdown("")).toBe(false);
    expect(hasRenderableMarkdown("   ")).toBe(false);
    expect(hasRenderableMarkdown(undefined)).toBe(false);
  });

  it("returns true for non-empty markdown", () => {
    expect(hasRenderableMarkdown("## 章節\n\n內文")).toBe(true);
  });
});
