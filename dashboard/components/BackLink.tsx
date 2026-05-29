"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

interface BackLinkProps {
  /** Fallback when history is empty (PWA standalone). */
  href: string;
  label?: string;
  className?: string;
}

/**
 * Prominent back control for PWA / mobile where browser chrome is absent.
 * Tries router.back() first; falls through to href via Link styling.
 */
export function BackLink({ href, label = "返回", className = "" }: BackLinkProps) {
  const router = useRouter();

  return (
    <div className={`mb-3 ${className}`.trim()}>
      <button
        type="button"
        onClick={() => {
          if (typeof window !== "undefined" && window.history.length > 1) {
            router.back();
            return;
          }
          router.push(href);
        }}
        className="inline-flex min-h-[44px] min-w-[44px] items-center gap-1.5 font-sans text-meta text-ink-soft transition-colors hover:text-accent"
      >
        <span aria-hidden className="text-lg leading-none">
          ←
        </span>
        <span>{label}</span>
      </button>
      <noscript>
        <Link href={href} className="font-sans text-meta text-accent underline-offset-4 hover:underline">
          {label}
        </Link>
      </noscript>
    </div>
  );
}
