"use client";

import { useEffect, useRef } from "react";

interface RevealOptions {
  /** Fraction of the element visible before it reveals. */
  threshold?: number;
  /** Stagger delay in ms applied via inline transition-delay. */
  delayMs?: number;
}

/**
 * Reveal-on-scroll for a single element. Returns a ref to attach to a node that
 * already carries the `reveal` class. The element is revealed once it scrolls
 * into view; if IntersectionObserver is unavailable it reveals immediately so
 * content is never left hidden.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>({
  threshold = 0.12,
  delayMs = 0,
}: RevealOptions = {}) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reveal = () => {
      if (delayMs > 0) el.style.transitionDelay = `${delayMs}ms`;
      el.setAttribute("data-revealed", "true");
    };

    if (typeof IntersectionObserver === "undefined") {
      reveal();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            reveal();
            observer.disconnect();
            break;
          }
        }
      },
      { threshold },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, delayMs]);

  return ref;
}
