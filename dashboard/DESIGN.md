# Tech Pulse Dashboard — Design System

Single source of truth for editorial and dense UI patterns in `dashboard/`.
Tokens live in `app/globals.css` and `tailwind.config.ts`.

## Modes

### Editorial (Today, Archive, Item)

- Warm paper + ink + oxblood accent — publication, not generic SaaS.
- Serif headlines (`font-serif`, `text-editorial-*`), reading column `max-w-column`.
- List density on Today theme sections: `InstantCardNewsList` + `InstantCard variant="list"` (title + one subline).
- Item detail (`/item/[id]`) is **hand-rolled** (`page.tsx` + `DeepInsightCard` for deep briefs), not `InstantCard variant="full"`.
- Kickers in Traditional Chinese where reader-facing (`主題`, `深度洞見`).

### Dense (Invest hub and sub-pages)

- `DensePageShell`, `section-band`, `StatCard`, `DataTable` (mobile card stack).
- Semantic colors: `text-pos` / `text-neg` / `text-warn` / `text-info` (+ `-bg`).
- Meta labels may use uppercase tracking; body copy stays readable 繁中.

## Color tokens

| Token | Role |
|-------|------|
| `--color-paper` | Page background |
| `--color-paper-tint` | Section bands |
| `--color-ink` | Primary text |
| `--color-ink-soft` | Secondary |
| `--color-ink-faint` | Timestamps (min 4.74:1 on paper) |
| `--color-rule` | Hairlines / dividers |
| `--color-accent` | Oxblood — kickers, links |
| `--color-pos/neg/warn/info` | Dense semantic |

## Typography

- **Serif**: headlines, Today masthead (`next/font` variables in layout).
- **Sans**: meta, dense tables, kickers.
- **Rhythm**: list rows `py-4` + `divide-rule`; section gaps `py-6` / `mt-10`.

## Component vocabulary

| Component | Use |
|-----------|-----|
| `Kicker` | Section label above headline |
| `Hairline` | Editorial divider |
| `InstantCard` | News **list** row (`variant="list"` via `InstantCardNewsList`). `full` exists in tests only. |
| `DeepInsightCard` | Long-form deep brief on Today |
| `NewsTakeawayBlock` | Portfolio angle; **outside** headline link |
| `ConfidenceBadge` | Only when `shouldShowConfidenceBadge` (warn/bad) |
| `DensePageShell` | Invest / portfolio / signals pages |
| `StatCard` | Ops and dense KPI tiles |

## InstantCard variants

| Variant | Where | Shows |
|---------|-------|--------|
| `list` | ThemeSection, HoldingNewsSection (`InstantCardNewsList`) | Kicker, title, one subline, compact footer |
| `full` | Tests only — not used on `/item/[id]` | Gated body / bilingual compare path in the component |

## Allowed accents

- **Deep insight left rail**: `border-l-2 border-accent` on `DeepInsightCard` only — editorial anchor, not a generic card border.
- **Drop cap** (`.editorial-dropcap`): lead paragraph only — `DeepInsightCard` first section / flat body and `/item/[id]` 中文摘要. One per article; never on list rows.
- **Motion tokens**: `--motion-fast|base|slow` + `--ease-out`; all motion auto-neutralised under `prefers-reduced-motion` (global rule in `globals.css`).
- **Chart palette**: `--chart-1..4` (Tailwind `text-chart-1`…) — single source for recharts + inline SVG.

## Do not

- Emoji as UI decoration (e.g. ticker rows use text label「代號」).
- Full `InstantCard` bodies on Today theme lists (scan-first).
- Show `ConfidenceBadge` on every row (noise).
- Placeholder-as-label on forms (use visible `<label>`).
- Expose pipeline/GCP jargon in reader empty states.
- Import Beautiful UI (beautifului.dev) charcoal / `#3d9aff` tokens, or copy their `--ink` names — this app uses `--color-ink` / Tailwind `text-ink`.
- Typewriter or fake token streaming on static JSON.
- Reuse `SourceTag` for news provenance (it is a dense data-quality lamp: `degraded` / `manual`).

## Empty states

- Reader-facing 繁中 copy + optional link (Archive, sub-page).
- No Firestore collection names in primary message.

## Related specs

- Portal data: `../docs/PORTAL_CONTRACT.md`
- Ops summary page: `../docs/superpowers/specs/2026-05-18-pulse-health-dashboard-design.md`
