import Link from "next/link";

import { displayTitle, type RenderableItem } from "@/lib/types";
import { bestTimestamp, formatRelativeDateline } from "@/lib/digest";

import { Hairline } from "./Hairline";
import { Kicker, MetaDot } from "./Kicker";

interface Props {
  theme: string;
  items: RenderableItem[];
  authenticated: boolean;
}

/**
 * Editorial section: kicker + serif h2, then a bilingual title list.
 * Each row shows source/date kicker, the English headline, and (when present)
 * the zh_summary directly underneath as a Chinese "對照" line. Tapping the
 * headline goes to the item detail page for the full read.
 */
export function ThemeSection({ theme, items }: Props) {
  return (
    <section className="pt-10">
      <header className="mb-2 space-y-2">
        <Kicker>Section</Kicker>
        <h2 className="font-serif text-[22px] leading-tight tracking-[-0.018em] text-ink sm:text-[26px]">
          {theme}
        </h2>
      </header>
      <Hairline />
      <ul className="divide-y divide-rule">
        {items.map((item) => (
          <li key={item.id} className="py-4">
            <Link
              href={`/item/${encodeURIComponent(item.id)}`}
              className="block space-y-2 hover:[&_h3]:underline"
            >
              <Kicker as="div" className="flex flex-wrap items-center">
                {item.source_name && <span>{item.source_name}</span>}
                {formatRelativeDateline(bestTimestamp(item)) && (
                  <>
                    {item.source_name && <MetaDot />}
                    <span className="tabular-nums">
                      {formatRelativeDateline(bestTimestamp(item))}
                    </span>
                  </>
                )}
              </Kicker>
              <h3 className="font-serif text-[19px] leading-snug tracking-[-0.015em] text-ink sm:text-[21px]">
                {displayTitle(item)}
              </h3>
              {item.zh_summary?.trim() && (
                <p className="font-sans text-[15px] leading-snug text-ink-soft">
                  {item.zh_summary}
                </p>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
