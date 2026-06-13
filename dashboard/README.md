# 科技脈搏 Dashboard

Next.js 15 web reader for the `tech-pulse` digest. Reads
`tech_pulse_memory_items` from Firestore (see
[`../docs/PORTAL_CONTRACT.md`](../docs/PORTAL_CONTRACT.md) for the schema) and
renders three views:

Design tokens and UI rules: [`DESIGN.md`](./DESIGN.md).

- `/` — latest digest, with 🧠 deep insights de-duped from the instant theme
  sections (mirrors the v1 Telegram formatter after PR1).
- `/archive` — last 14 days grouped by delivery day.
- `/health` — ops summary of delivered content counts and score distribution.
- `/item/[id]` — single-doc detail (full deep brief or expanded instant card).
- `/invest` — investment hub (portfolio, signals, earnings, macro, calibration summaries).
- `/earnings` — earnings radar list (`tech_pulse_earnings_reports`).
- `/earnings/[ticker]` — per-ticker filings + same-tier comparison.
- `/earnings/report/[reportId]` — v3 six-section deep report (Markdown).
- `/portfolio` — holdings, theme exposure, allocation drift (`config/portfolio.yaml`).

After editing `../config/portfolio.yaml`, run from repo root:

```bash
python3 scripts/export_portfolio_json.py
```

Optional `FINNHUB_API_KEY` in `.env.local` enables live quotes on `/portfolio` and
`GET /api/v1/portfolio`; without it, market values fall back to cost basis.

## 公開讀（乙 + B）

若設定 `DASHBOARD_PUBLIC_READ=true`（或 `1`）：

- **匿名訪客**：可看標題與公開摘要（`zh_summary` 優先，否則截斷英文）；`sitemap.xml` /
  `robots.txt` 與每頁 `metadata` 僅使用摘要層級，不把完整 `summary` 放進 HTML。
- **完整繁中正文**：登入後讀取 Firestore `zh_body`（pipeline 寫入）；舊稿可能僅有英文 `summary`，Dashboard 會 fallback。帳密與 `DASHBOARD_BASIC_AUTH_USER` /
  `DASHBOARD_BASIC_AUTH_PASS` 相同；登入後寫入簽名 cookie（需
  `DASHBOARD_SESSION_SECRET`，建議至少 32 字元）。
- **Middleware**：公開讀模式下 **不再** 對全站套用 HTTP Basic（避免與 SEO 衝突）。
  未啟用公開讀時，行為與先前一致（有設帳密則全站 Basic）。

部署公開站請設定 **`NEXT_PUBLIC_SITE_URL`**（公開 HTTPS origin，無結尾斜線），供
`metadataBase` 與 sitemap canonical 使用。

## Quick start

```bash
cd dashboard
cp .env.example .env.local
# fill in either FIREBASE_SERVICE_ACCOUNT_JSON or run
#   gcloud auth application-default login
pnpm install        # or npm install / yarn install
pnpm dev
```

### PWA icons

Brand icons live in `public/` and are referenced by `app/manifest.ts`. Regenerate from the SVG wordmark:

```bash
cd dashboard
npm install          # includes devDependency sharp
npm run gen-icons    # writes icon-192/512, maskable-512, apple-touch-icon
```

Open <http://localhost:3000>. With `DASHBOARD_BASIC_AUTH_USER` /
`DASHBOARD_BASIC_AUTH_PASS` set **and** `DASHBOARD_PUBLIC_READ` unset, the
middleware challenges with HTTP Basic Auth; leave both blank to disable the
gate during local dev. See **公開讀（乙 + B）** above when `DASHBOARD_PUBLIC_READ`
is enabled.

## Architecture

```
dashboard/
├─ app/
│  ├─ layout.tsx         # 根：字型 + globals（無主站導覽）
│  ├─ (app)/layout.tsx   # 主站 shell：Today / Archive / AuthNav
│  ├─ (app)/page.tsx
│  ├─ (app)/archive/page.tsx
│  ├─ (app)/item/[id]/page.tsx
│  ├─ (auth)/login/      # 獨立登入版面（無主站導覽）
│  ├─ sitemap.ts / robots.ts
│  ├─ api/revalidate/   # webhook for the pipeline to flush ISR
│  ├─ api/v1/           # read-only REST (items, digest, tickers, facets, health)
│  └─ api/auth/         # reader login + logout (public read mode)
├─ lib/
│  ├─ firestore.ts      # Admin SDK init + readers (server-only)
│  ├─ types.ts          # Zod schema for MemoryItem + ISO coercion
│  ├─ digest.ts         # theme grouping / dedupe / badge logic
│  ├─ format-numbers.ts # fmtNum / fmtPctPlain / fmtPctSigned / fmtUsd (dense cards)
│  └─ login-path.ts     # loginReturnHref() for reader cookie flows
├─ components/          # presentation, no Firestore imports
│  ├─ BrandMark.tsx     # Nav rail wordmark
│  └─ InstantCardNewsList.tsx  # shared list for ThemeSection / HoldingNewsSection
└─ middleware.ts        # Basic Auth gate (Edge); skipped when public read on
```

### Quality gate

```bash
npm run lint && npm run typecheck && npm run test && npm run build
```

Recent a11y fixes: global `:focus-visible`, login error `role="alert"`, Relationships 10-K via `<details>`, calibration charts with `role="img"` + `aria-label`.

The `lib/digest.ts` module is a TypeScript port of
`delivery/message_formatter.py`. Both must agree on:

- theme keyword tables,
- score↔confidence badge mapping (`HIGH_SCORE_CONFIDENCE_FLOOR = 7.2`),
- deep-vs-instant dedupe key (source_url, then case-insensitive title).

If the algorithm grows complex, promote the canonical selection to a
Firestore `tech_pulse_digests/{digest_id}` snapshot (additive — does not
break Portal contract v1) and have both consumers read it.

## REST API (`/api/v1`)

唯讀 JSON，與 [`docs/PORTAL_CONTRACT.md`](../docs/PORTAL_CONTRACT.md) 欄位對齊。

| 路徑 | 說明 |
|------|------|
| `GET /api/v1/health` | 服務與最新 `delivered_at` |
| `GET /api/v1/items` | 列表；`limit`, `since`, `category`, `month`, `ticker`, `kind` |
| `GET /api/v1/items/{id}` | 單篇 |
| `GET /api/v1/digest/today` | 今日編排（同首頁 snapshot 合併邏輯） |
| `GET /api/v1/tickers` | 熱門代號；`scope=today\|archive` |
| `GET /api/v1/archive/facets` | 歸檔 facet 計數 |
| `GET /api/v1/earnings` | 財報列表；`limit`, `ticker`, `max_tier` |
| `GET /api/v1/earnings/report/{reportId}` | 單篇財報（含 v3 欄位） |
| `GET /api/v1/earnings/upcoming` | 行事曆（`days`；Finnhub 或 Firestore fallback） |
| `GET /api/v1/earnings/{symbol}/insight` | 最新 v3 財報 + `report_url_path` |
| `GET /api/v1/earnings/watchlist` | `earnings_watchlist.yaml` 匯出 |
| `GET /api/v1/earnings/calendar` | 相容別名（`horizon` ≈ `days`） |
| `GET /api/v1/earnings/ai-infra` | 篩選 `ai_infra_signal` |
| `GET /api/v1/news/digest` | Portal 快訊（`date`, `limit`）；含 `summary` 給 Q-Silicon 日報 |
| `GET /api/v1/news/deep` | 深度稿（`pillar`, `limit`） |
| `GET /api/v1/news/deep/{itemId}` | 單篇深度稿 |
| `GET /api/v1/news/themes` | 標籤聚合 |

Q-Silicon 整合說明：[`../docs/QSILICON_INTEGRATION.md`](../docs/QSILICON_INTEGRATION.md)。

**授權**

- 公開讀模式：匿名可得 `title_zh` + 公開摘要；`Authorization: Bearer <API_READ_TOKEN>` 或 reader cookie → 完整 `summary_en` / `zh_body`。
- 非公開讀：須設定 `API_READ_TOKEN` 並帶 Bearer。

```bash
curl -s -H "Authorization: Bearer $API_READ_TOKEN" \
  "https://your-dashboard.vercel.app/api/v1/items?limit=5&ticker=GOOGL"
```

## Deployment (Vercel)

Production 環境變數勾選表與驗證指令：[`../docs/DEPLOY_CHECKLIST.md`](../docs/DEPLOY_CHECKLIST.md)。
財報 v3 僅需 Firestore 讀取（**不必**在 Vercel 設 `FINNHUB_API_KEY`）；Pipeline 端 Finnhub 設定見 [`../docs/EARNINGS_ENV.md`](../docs/EARNINGS_ENV.md)。

1. Import the repo, point project root at `dashboard/`.
2. Build command: `pnpm build`; output: `.next`.
3. Set env vars from `.env.example`:
   - `FIREBASE_SERVICE_ACCOUNT_JSON` — base64-encoded JSON of a service
     account with `roles/datastore.viewer`. **Server-only** — never expose
     in client components.
   - `DASHBOARD_BASIC_AUTH_USER` / `DASHBOARD_BASIC_AUTH_PASS` — reader
     credentials (Basic gate when public read **off**; same pair for `/login`
     when public read **on**).
   - `DASHBOARD_PUBLIC_READ` — set `true` for public title/summary + cookie
     gated body (see README section above).
   - `DASHBOARD_SESSION_SECRET` — HMAC secret for reader cookie when public read
     is on.
   - `NEXT_PUBLIC_SITE_URL` — canonical site origin for SEO (recommended in
     production).
   - `REVALIDATE_TOKEN` — shared secret for the ISR webhook.
4. After each pipeline run, POST:
   ```bash
   curl -X POST "https://<host>/api/revalidate?path=/" \
     -H "x-revalidate-token: $REVALIDATE_TOKEN"
   curl -X POST "https://<host>/api/revalidate?path=/earnings" \
     -H "x-revalidate-token: $REVALIDATE_TOKEN"
   ```
   Pipeline [`delivery/revalidate.py`](../delivery/revalidate.py) also revalidates `/earnings` by default.
   The pipeline does this automatically when both env vars are set:
   - `DASHBOARD_REVALIDATE_URL` — full webhook URL, e.g.
     `https://your-dashboard.vercel.app/api/revalidate`
   - `DASHBOARD_REVALIDATE_TOKEN` — same value as `REVALIDATE_TOKEN` above

   Hook: [`delivery/revalidate.py`](../delivery/revalidate.py). Unset either
   variable to skip the call (local / CI runs).

### Service account provisioning

Run the helper script once from the repo root to create a read-only SA and
download a key:

```bash
PROJECT_ID=my-tech-pulse-agent-494715 ./scripts/setup_dashboard_sa.sh
```

It creates `tech-pulse-dashboard@<project>.iam.gserviceaccount.com` with
`roles/datastore.viewer` and writes the key to `dashboard-sa.json`
(gitignored at the repo root). Base64-encode it into the Vercel
`FIREBASE_SERVICE_ACCOUNT_JSON` env var.

## Read-only contract

The dashboard never writes back to Firestore. It also tolerates missing
optional fields per `docs/PORTAL_CONTRACT.md` — `themes` is reconstructed
locally from `category` because the pipeline does not yet write that array.
