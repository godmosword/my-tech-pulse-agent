# 科技脈搏 Dashboard

Next.js 15 web reader for the `tech-pulse` digest. Reads
`tech_pulse_memory_items` from Firestore (see
[`../docs/PORTAL_CONTRACT.md`](../docs/PORTAL_CONTRACT.md) for the schema) and
renders three views:

- `/` — latest digest, with 🧠 deep insights de-duped from the instant theme
  sections (mirrors the v1 Telegram formatter after PR1).
- `/archive` — last 14 days grouped by delivery day.
- `/item/[id]` — single-doc detail (full deep brief or expanded instant card).

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
`DASHBOARD_BASIC_AUTH_PASS` set, the middleware challenges with HTTP Basic
Auth; leave both blank to disable the gate during local dev.

## Architecture

```
dashboard/
├─ app/                 # Next.js App Router pages
│  ├─ page.tsx          # latest digest (ISR 5min)
│  ├─ archive/page.tsx  # 14-day timeline
│  ├─ item/[id]/page.tsx
│  └─ api/revalidate/   # webhook for the pipeline to flush ISR
├─ lib/
│  ├─ firestore.ts      # Admin SDK init + readers (server-only)
│  ├─ types.ts          # Zod schema for MemoryItem + ISO coercion
│  └─ digest.ts         # theme grouping / dedupe / badge logic
├─ components/          # presentation, no Firestore imports
└─ middleware.ts        # Basic Auth gate (Edge runtime)
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
   - `DASHBOARD_BASIC_AUTH_USER` / `DASHBOARD_BASIC_AUTH_PASS` — Basic Auth
     credentials.
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
