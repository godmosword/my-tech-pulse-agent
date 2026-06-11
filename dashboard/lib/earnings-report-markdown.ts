export type MarkdownTocItem = {
  id: string;
  text: string;
  level: 2 | 3;
};

/** Strip lightweight inline markdown for TOC labels. */
export function stripInlineMarkdown(text: string): string {
  return text
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

/** Build a stable DOM id for a heading (supports CJK). */
export function slugifyHeading(text: string, used: Set<string> = new Set()): string {
  const cleaned = stripInlineMarkdown(text);
  const base =
    cleaned
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^\w\u4e00-\u9fff-]+/g, "")
      .slice(0, 48) || "section";

  let id = base;
  let suffix = 2;
  while (used.has(id)) {
    id = `${base}-${suffix}`;
    suffix += 1;
  }
  used.add(id);
  return id;
}

/** Extract h2/h3 headings in document order for table of contents. */
export function extractMarkdownHeadings(markdown: string): MarkdownTocItem[] {
  const items: MarkdownTocItem[] = [];
  const used = new Set<string>();

  for (const line of markdown.split("\n")) {
    const trimmed = line.trim();
    const h2 = /^##\s+(.+)$/.exec(trimmed);
    if (h2) {
      const text = stripInlineMarkdown(h2[1]);
      if (!text) continue;
      items.push({ level: 2, text, id: slugifyHeading(text, used) });
      continue;
    }
    const h3 = /^###\s+(.+)$/.exec(trimmed);
    if (h3) {
      const text = stripInlineMarkdown(h3[1]);
      if (!text) continue;
      items.push({ level: 3, text, id: slugifyHeading(text, used) });
    }
  }

  return items;
}

export function hasRenderableMarkdown(content: string | null | undefined): boolean {
  return Boolean(content?.trim());
}
