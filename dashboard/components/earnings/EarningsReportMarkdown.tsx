"use client";

import { useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

import {
  extractMarkdownHeadings,
  type MarkdownTocItem,
} from "@/lib/earnings-report-markdown";

type Props = {
  content: string;
};

function scrollToHeading(id: string) {
  const el = document.getElementById(id);
  el?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function TableOfContents({
  headings,
  className,
}: {
  headings: MarkdownTocItem[];
  className?: string;
}) {
  if (headings.length === 0) {
    return null;
  }

  return (
    <nav aria-label="章節目錄" className={className}>
      <p className="font-sans text-meta uppercase tracking-wide text-ink-faint">章節</p>
      <ul className="mt-3 space-y-2 border-l border-rule pl-3">
        {headings.map((item) => (
          <li key={item.id} className={item.level === 3 ? "pl-3" : undefined}>
            <button
              type="button"
              onClick={() => scrollToHeading(item.id)}
              className="text-left font-sans text-meta text-ink-soft transition-colors hover:text-accent"
            >
              {item.text}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function MobileTableOfContents({ headings }: { headings: MarkdownTocItem[] }) {
  if (headings.length === 0) {
    return null;
  }

  return (
    <div className="mb-4 lg:hidden">
      <label htmlFor="earnings-report-toc" className="font-sans text-meta text-ink-faint">
        跳至章節
      </label>
      <select
        id="earnings-report-toc"
        className="mt-1 w-full rounded-md border border-rule bg-paper px-3 py-2 font-sans text-body text-ink"
        defaultValue=""
        onChange={(event) => {
          const id = event.target.value;
          if (id) scrollToHeading(id);
        }}
      >
        <option value="" disabled>
          選擇章節…
        </option>
        {headings.map((item) => (
          <option key={item.id} value={item.id}>
            {item.level === 3 ? `　${item.text}` : item.text}
          </option>
        ))}
      </select>
    </div>
  );
}

export function EarningsReportMarkdown({ content }: Props) {
  const headings = useMemo(() => extractMarkdownHeadings(content), [content]);
  const headingIds = useMemo(() => headings.map((item) => item.id), [headings]);
  const headingIndexRef = useRef(0);
  headingIndexRef.current = 0;

  const nextHeadingId = () => {
    const id = headingIds[headingIndexRef.current];
    headingIndexRef.current += 1;
    return id;
  };

  const components: Components = {
    h2: ({ children }) => {
      const id = nextHeadingId();
      return (
        <h2
          id={id}
          className="mt-10 scroll-mt-6 font-serif text-editorial-headline text-ink first:mt-0"
        >
          {children}
        </h2>
      );
    },
    h3: ({ children }) => {
      const id = nextHeadingId();
      return (
        <h3
          id={id}
          className="mt-8 scroll-mt-6 font-serif text-[20px] font-semibold leading-snug text-ink"
        >
          {children}
        </h3>
      );
    },
    p: ({ children }) => (
      <p className="mt-4 font-sans text-editorial-body text-ink-soft">{children}</p>
    ),
    ul: ({ children }) => (
      <ul className="mt-4 list-disc space-y-2 pl-5 font-sans text-editorial-body text-ink-soft">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="mt-4 list-decimal space-y-2 pl-5 font-sans text-editorial-body text-ink-soft">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="leading-relaxed">{children}</li>,
    strong: ({ children }) => (
      <strong className="font-semibold text-ink">{children}</strong>
    ),
    a: ({ href, children }) => (
      <a
        href={href}
        className="text-accent underline-offset-2 hover:underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    ),
    table: ({ children }) => (
      <div className="mt-4 overflow-x-auto">
        <table className="data-table">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead>{children}</thead>,
    tbody: ({ children }) => <tbody>{children}</tbody>,
    tr: ({ children }) => <tr>{children}</tr>,
    // GFM tables are column-header tables; scope="col" is correct here.
    // Row-header support is out of scope (remark-gfm does not emit row headers).
    th: ({ children }) => <th scope="col">{children}</th>,
    td: ({ children }) => <td>{children}</td>,
  };

  return (
    <div className="mt-6 lg:grid lg:grid-cols-[minmax(180px,220px)_minmax(0,1fr)] lg:gap-10">
      <TableOfContents
        headings={headings}
        className="hidden lg:block lg:sticky lg:top-6 lg:self-start"
      />
      <div className="min-w-0">
        <MobileTableOfContents headings={headings} />
        <article className="earnings-report-md max-w-column">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {content}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
