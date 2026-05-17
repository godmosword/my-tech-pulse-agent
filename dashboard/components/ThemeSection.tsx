import { THEME_EMOJI } from "@/lib/digest";
import type { RenderableItem } from "@/lib/types";
import { InstantCard } from "./InstantCard";

interface Props {
  theme: string;
  items: RenderableItem[];
}

export function ThemeSection({ theme, items }: Props) {
  const emoji = THEME_EMOJI[theme] ?? "📡";
  return (
    <section className="space-y-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink-muted">
        <span aria-hidden>━━━</span>
        <span>
          {emoji} {theme}
        </span>
        <span aria-hidden>━━━</span>
      </h2>
      <div className="space-y-3">
        {items.map((item) => (
          <InstantCard key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}
