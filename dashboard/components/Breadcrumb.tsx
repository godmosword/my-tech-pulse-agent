import Link from "next/link";

export type Crumb = { label: string; href?: string };

export function Breadcrumb({ items }: { items: Crumb[] }) {
  if (!items.length) return null;

  return (
    <nav aria-label="Breadcrumb" className="mb-4 font-sans text-meta tracking-wide text-ink-faint">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`} className="flex items-center gap-x-2">
              {i > 0 && (
                <span aria-hidden className="text-ink-faint">
                  /
                </span>
              )}
              {isLast || !item.href ? (
                <span className="uppercase tracking-[0.1em] text-ink-soft">{item.label}</span>
              ) : (
                <Link
                  href={item.href}
                  className="uppercase tracking-[0.1em] hover:text-accent"
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
