# Tech Pulse Dashboard — Design System

Single source of truth for editorial and dense UI patterns in `dashboard/`.
Tokens live in `app/globals.css` and `tailwind.config.ts`.

## Modes

### Editorial (Today, Archive, Item)

- Warm paper + ink + oxblood accent — publication, not generic SaaS.
- Serif headlines (`font-serif`, `text-editorial-*`), reading column `max-w-column`.
- List density on Today theme sections: `InstantCard variant="list"` (title + one subline).
- Full article density on `/item/[id]`: `InstantCard variant="full"`.
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
| `InstantCard` | News row; `list` vs `full` variants |
| `DeepInsightCard` | Long-form deep brief on Today |
| `NewsTakeawayBlock` | Portfolio angle; **outside** headline link |
| `ConfidenceBadge` | Only when `shouldShowConfidenceBadge` (warn/bad) |
| `DensePageShell` | Invest / portfolio / signals pages |
| `StatCard` | Ops and dense KPI tiles |

## InstantCard variants

| Variant | Where | Shows |
|---------|-------|--------|
| `list` | ThemeSection, HoldingNewsSection | Kicker, title, one subline, compact footer |
| `full` | Item detail | zh_summary, gated zh_body, expand analysis, 阅读原文 |

## Allowed accents

- **Deep insight left rail**: `border-l-2 border-accent` on `DeepInsightCard` only — editorial anchor, not a generic card border.

## Do not

- Emoji as UI decoration (e.g. ticker rows use text label「代號」).
- Full `InstantCard` bodies on Today theme lists (scan-first).
- Show `ConfidenceBadge` on every row (noise).
- Placeholder-as-label on forms (use visible `<label>`).
- Expose pipeline/GCP jargon in reader empty states.

## Empty states

- Reader-facing 繁中 copy + optional link (Archive, sub-page).
- No Firestore collection names in primary message.

## Related specs

- Portal data: `../docs/PORTAL_CONTRACT.md`
- Ops summary page: `../docs/superpowers/specs/2026-05-18-pulse-health-dashboard-design.md`
