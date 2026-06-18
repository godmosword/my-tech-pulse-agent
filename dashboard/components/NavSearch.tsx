"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

type SearchNewsResult = {
  id: string;
  title: string;
  href: string;
};

type SearchEarningsResult = {
  ticker: string;
  company: string;
  quarter_label: string;
  href: string;
};

type SearchResponse = {
  query: string;
  news: SearchNewsResult[];
  earnings: SearchEarningsResult[];
};

type Props = {
  variant: "rail" | "mobile";
  onClose?: () => void;
};

export function NavSearch({ variant, onClose }: Props) {
  const router = useRouter();
  const listboxId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const flatCount = (results?.news.length ?? 0) + (results?.earnings.length ?? 0);
  const showPanel = open && debouncedQuery.length > 0;

  useEffect(() => {
    if (variant === "mobile") {
      inputRef.current?.focus();
    }
  }, [variant]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!debouncedQuery) {
      setResults(null);
      setLoading(false);
      setError(null);
      setActiveIndex(-1);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const params = new URLSearchParams({ q: debouncedQuery });
        const res = await fetch(`/api/search?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!res.ok) {
          setError("搜尋失敗，請稍後再試。");
          setResults(null);
          return;
        }
        const body = (await res.json()) as SearchResponse;
        setResults(body);
        setActiveIndex(body.news.length + body.earnings.length > 0 ? 0 : -1);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError("搜尋失敗，請稍後再試。");
        setResults(null);
      } finally {
        setLoading(false);
      }
    })();

    return () => controller.abort();
  }, [debouncedQuery]);

  useEffect(() => {
    if (!showPanel) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [showPanel]);

  const closeSearch = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
    if (variant === "mobile") {
      setQuery("");
      setDebouncedQuery("");
      setResults(null);
      onClose?.();
    }
  }, [onClose, variant]);

  const navigateTo = useCallback(
    (href: string) => {
      closeSearch();
      router.push(href);
    },
    [closeSearch, router],
  );

  const flatOptions = useMemo(() => {
    if (!results) return [];
    return [
      ...results.news.map((item) => ({ href: item.href })),
      ...results.earnings.map((item) => ({ href: item.href })),
    ];
  }, [results]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeSearch();
      inputRef.current?.blur();
      return;
    }

    if (!showPanel || flatOptions.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % flatOptions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) =>
        prev <= 0 ? flatOptions.length - 1 : prev - 1,
      );
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      const option = flatOptions[activeIndex];
      if (option) navigateTo(option.href);
    }
  };

  const activeDescendant =
    activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined;

  const clearQuery = useCallback(() => {
    setQuery("");
    setDebouncedQuery("");
    setResults(null);
    setActiveIndex(-1);
    inputRef.current?.focus();
  }, []);

  const inputClass =
    "w-full rounded border border-rule bg-paper pl-9 pr-9 py-2 font-sans text-body text-ink placeholder:text-ink-faint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

  const panel = showPanel ? (
    <div
      id={listboxId}
      role="listbox"
      aria-label="搜尋結果"
      className="absolute left-0 right-0 z-50 mt-2 max-h-80 overflow-y-auto rounded border border-rule bg-paper shadow-sm"
    >
      {loading && (
        <p className="px-3 py-2 font-sans text-meta text-ink-faint">搜尋中…</p>
      )}
      {error && (
        <p className="px-3 py-2 font-sans text-body text-neg" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && flatCount === 0 && (
        <p className="px-3 py-2 font-sans text-body text-ink-soft">
          找不到符合的新聞或財報
        </p>
      )}
      {!loading && !error && results && results.news.length > 0 && (
        <div className="border-b border-rule px-3 py-2">
          <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
            新聞
          </p>
          <ul>
            {results.news.map((item, index) => {
              const selected = activeIndex === index;
              return (
                <li key={item.id}>
                  <Link
                    id={`${listboxId}-option-${index}`}
                    role="option"
                    aria-selected={selected}
                    href={item.href}
                    className={`block rounded px-2 py-2 font-sans text-body text-ink hover:bg-paper-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                      selected ? "bg-paper-tint" : ""
                    }`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo(item.href);
                    }}
                  >
                    {item.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {!loading && !error && results && results.earnings.length > 0 && (
        <div className="px-3 py-2">
          <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
            財報
          </p>
          <ul>
            {results.earnings.map((item, index) => {
              const flatIndex = results.news.length + index;
              const selected = activeIndex === flatIndex;
              return (
                <li key={item.ticker}>
                  <Link
                    id={`${listboxId}-option-${flatIndex}`}
                    role="option"
                    aria-selected={selected}
                    href={item.href}
                    className={`block rounded px-2 py-2 hover:bg-paper-tint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                      selected ? "bg-paper-tint" : ""
                    }`}
                    onMouseEnter={() => setActiveIndex(flatIndex)}
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo(item.href);
                    }}
                  >
                    <span className="font-mono text-body text-ink">{item.ticker}</span>
                    {(item.quarter_label || item.company) && (
                      <span className="ml-2 font-sans text-meta text-ink-soft">
                        {item.quarter_label || item.company}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <p className="border-t border-rule px-3 py-2 font-sans text-meta text-ink-faint">
        代號精確比對 · 標題與內文關鍵字
      </p>
    </div>
  ) : null;

  return (
    <div
      ref={rootRef}
      className={variant === "mobile" ? "relative w-full" : "relative mt-6"}
    >
      <label htmlFor={`${listboxId}-input`} className="sr-only">
        搜尋新聞或財報
      </label>
      <div className={variant === "mobile" ? "flex items-center gap-2" : ""}>
        <div className="relative flex-1">
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="none"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint"
          >
            <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.6" />
            <path
              d="m14 14 3.5 3.5"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
          <input
            ref={inputRef}
            id={`${listboxId}-input`}
            type="search"
            role="combobox"
            aria-expanded={showPanel}
            aria-controls={showPanel ? listboxId : undefined}
            aria-activedescendant={activeDescendant}
            aria-autocomplete="list"
            placeholder="搜尋代號或標題…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            className={inputClass}
            autoComplete="off"
          />
          {query && (
            <button
              type="button"
              aria-label="清除搜尋"
              onClick={clearQuery}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 font-sans text-meta text-ink-faint hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
            >
              ✕
            </button>
          )}
        </div>
        {variant === "mobile" && (
          <button
            type="button"
            aria-label="關閉搜尋"
            className="shrink-0 rounded border border-rule px-2 py-2 font-sans text-meta text-ink-faint hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            onClick={closeSearch}
          >
            關閉
          </button>
        )}
      </div>
      {panel}
    </div>
  );
}
