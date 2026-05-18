# 科技脈搏 Dashboard

Next.js 15 web reader for the `tech-pulse` digest. Reads
`tech_pulse_memory_items` from Firestore (see
[`../docs/PORTAL_CONTRACT.md`](../docs/PORTAL_CONTRACT.md) for the schema) and
renders three views:

- `/` — latest digest, with 🧠 deep insights de-duped from the instant theme
  sections (mirrors the v1 Telegram formatter after PR1).
- `/archive` — last 14 days grouped by delivery day.
- `/item/[id]` — single-doc detail (full deep brief or expanded instant card).

## 公開讀（乙 + B）

若設定 `DASHBOARD_PUBLIC_READ=true`（或 `1`）：

- **匿名訪客**：可看標題與公開摘要（`zh_summary` 優先，否則截斷英文）；`sitemap.xml` /
  `robots.txt` 與每頁 `metadata` 僅使用摘要層級，不把完整 `summary` 放進 HTML。
- **完整正文**：使用 `/login` 表單登入；帳密與 `DASHBOARD_BASIC_AUTH_USER` /
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

Open <http://localhost:3000>. With `DASHBOARD_BASIC_AUTH_USER` /
`DASHBOARD_BASIC_AUTH_PASS` set **and** `DASHBOARD_PUBLIC_READ` unset, the
middleware challenges with HTTP Basic Auth; leave both blank to disable the
gate during local dev. See **公開讀（乙 + B）** above when `DASHBOARD_PUBLIC_READ`
is enabled.

## Architecture

```
dashboard/
├─ app/                 # Next.js App Router pages
│  ├─ page.tsx          # latest digest (ISR 5min)
│  ├─ archive/page.tsx  # 14-day timeline
│  ├─ item/[id]/page.tsx
│  ├─ login/page.tsx     # reader login (public read mode)
│  ├─ sitemap.ts / robots.ts
│  ├─ api/revalidate/   # webhook for the pipeline to flush ISR
│  └─ api/auth/         # reader login + logout (public read mode)
├─ lib/
│  ├─ firestore.ts      # Admin SDK init + readers (server-only)
│  ├─ types.ts          # Zod schema for MemoryItem + ISO coercion
│  └─ digest.ts         # theme grouping / dedupe / badge logic
├─ components/          # presentation, no Firestore imports
└─ middleware.ts        # Basic Auth gate (Edge); skipped when public read on
```

The `lib/digest.ts` module is a TypeScript port of
`delivery/message_formatter.py`. Both must agree on:

- theme keyword tables,
- score↔confidence badge mapping (`HIGH_SCORE_CONFIDENCE_FLOOR = 7.2`),
- deep-vs-instant dedupe key (source_url, then case-insensitive title).

If the algorithm grows complex, promote the canonical selection to a
Firestore `tech_pulse_digests/{digest_id}` snapshot (additive — does not
break Portal contract v1) and have both consumers read it.

## Deployment (Vercel)

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
   ```
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
