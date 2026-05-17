import type { RenderableItem } from "@/lib/types";
import { Hairline } from "./Hairline";
import { InstantCard } from "./InstantCard";
import { Kicker } from "./Kicker";

interface Props {
  theme: string;
  items: RenderableItem[];
}

/**
 * Editorial section: a kicker label + serif h2 above a stack of items, with
 * hairline rules between items rather than card boxes. The section header
 * carries the theme name; the kicker labels it as a section, so we don't need
 * the bracket emojis the Telegram digest uses.
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
      <div className="divide-y divide-rule">
        {items.map((item) => (
          <InstantCard key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}
