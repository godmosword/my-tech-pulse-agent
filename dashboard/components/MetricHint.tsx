"use client";

import { useEffect, useId, useRef, useState } from "react";

import { type MetricKey, metricHint } from "@/lib/metric-glossary";

/**
 * Small accessible "what is this" hint for a quant metric. Not hover-only: a
 * real <button> toggles a popover on click / tap / Enter / Space, so touch and
 * keyboard users get the explanation too. Escape and outside-click close it.
 * The explanation text lives in lib/metric-glossary (single source).
 */
export function MetricHint({
  metric,
  className = "",
}: {
  metric: MetricKey;
  className?: string;
}) {
  const info = metricHint(metric);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span ref={wrapRef} className={`relative inline-block ${className}`}>
      <button
        type="button"
        aria-label={`「${info.label_zh}」說明`}
        aria-expanded={open}
        aria-controls={panelId}
        aria-describedby={open ? panelId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-rule text-[10px] leading-none text-ink-faint hover:border-accent hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        i
      </button>
      {open && (
        <span
          id={panelId}
          role="note"
          className="section-band absolute left-1/2 top-6 z-10 w-64 max-w-[16rem] -translate-x-1/2 px-3 py-2 font-sans text-meta normal-case tracking-normal text-ink-soft"
        >
          <span className="block font-semibold text-ink">{info.label_zh}</span>
          <span className="mt-1 block">{info.hint_zh}</span>
        </span>
      )}
    </span>
  );
}
