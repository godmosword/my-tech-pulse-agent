"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Client-side link that defeats Next's router cache. Uses router.push +
 * router.refresh so server components re-render even when the URL is already
 * the current route (e.g. clicking "清除" from `/archive?category=x` back to
 * `/archive`). A plain `<Link>` was no-oping due to the App Router cache.
 */
export function ClearFiltersLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: ReactNode;
}) {
  const router = useRouter();
  return (
    <a
      href={href}
      className={className}
      onClick={(e) => {
        e.preventDefault();
        router.push(href);
        router.refresh();
      }}
    >
      {children}
    </a>
  );
}
