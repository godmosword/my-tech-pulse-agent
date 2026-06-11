"use client";

import { useState } from "react";

import { BrandMark } from "./BrandMark";
import { NavSearch } from "./NavSearch";
import { ThemeToggle } from "./ThemeToggle";

function SearchIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </svg>
  );
}

export function MobileMastheadTop() {
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <BrandMark variant="mobile" className="min-w-0" />
        <div className="flex shrink-0 items-center gap-2 pt-1">
          {!searchOpen && (
            <button
              type="button"
              aria-label="開啟搜尋"
              className="rounded border border-rule p-2 text-ink-soft hover:border-accent hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              onClick={() => setSearchOpen(true)}
            >
              <SearchIcon className="h-4 w-4" />
            </button>
          )}
          <span className="sr-only">顯示模式</span>
          <ThemeToggle />
        </div>
      </div>
      {searchOpen && (
        <NavSearch variant="mobile" onClose={() => setSearchOpen(false)} />
      )}
    </>
  );
}
