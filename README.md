# tech-pulse

AI-powered tech news intelligence pipeline. Scrapes trending tech news from RSS feeds and social
platforms, runs multi-layer Gemini agent analysis, parses earnings reports from SEC EDGAR, and
delivers structured summaries to a Telegram channel (#科技脈搏).

## Quick Start

```bash
pip install -e .
cp .env.example .env   # fill in your keys
python main.py                   # Cloud Run Job entry point
python scripts/preflight.py      # production config check
```

Local setup (`.env`, ADC, Dashboard): [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md).

## Pipeline Overview

```
RSS / Social / SEC EDGAR
        ↓
  Heuristic Prefilter + Gemini Flash Score Gate
  → eliminates low-signal items before expensive calls
        ↓
  Gemini Pro Extractor (with semantic pre-dedup)
  → structured arguments with confidence scores
        ↓
  Gemini Pro Reviewer + Synthesizer
  → cross-article themes + daily digest narrative
        ↓
  Smart Telegram Delivery (#科技脈搏)
  → HTML parse_mode, theme-aware chunking at 4096 char boundaries
        ↓
  Firestore memory archive (optional) + Dashboard ISR webhook
  → Next.js reader at dashboard/ (Vercel)
```

**Smart message delivery**: Long digests are split at newline (theme) boundaries when possible. Messages stay under Telegram's 4096 character limit with **HTML** `parse_mode` (dynamic text is escaped in `message_formatter.py`). Each chunk includes boundary validation and configurable inter-message delays (`TELEGRAM_CHUNK_DELAY_MS`).

**Web dashboard**: [`dashboard/README.md`](dashboard/README.md) reads `tech_pulse_memory_items` from Firestore. After each successful delivery, the pipeline can POST to `/api/revalidate` when `DASHBOARD_REVALIDATE_URL` and `DASHBOARD_REVALIDATE_TOKEN` are set ([`delivery/revalidate.py`](delivery/revalidate.py)).

Earnings reports follow a dedicated sub-pipeline (`earnings_v3` in Firestore
`tech_pulse_earnings_reports`). SEC XBRL is the source of truth for **actual**
numbers; Finnhub supplies consensus, calendar, quote, and transcripts when enabled.

```
SEC EDGAR RSS → XBRL headline facts → narrative (8-K text)
             → Finnhub estimates/quote/calendar (optional)
             → scorecard (basis-aligned surprise) → guidance/segments/transcript
             → analyzer + conclusion → six-section Markdown
             → Firestore + Telegram + Dashboard /earnings/report/{id}
```

See [`docs/EARNINGS_PORTAL.md`](docs/EARNINGS_PORTAL.md),
[`docs/EARNINGS_API_EVALUATION.md`](docs/EARNINGS_API_EVALUATION.md), and
[`docs/EARNINGS_ENV.md`](docs/EARNINGS_ENV.md) (API keys & env for v3).

## Environment Variables

| Variable              | Required | Description                   |
|-----------------------|----------|-------------------------------|
| `GEMINI_API_KEY`      | ✅       | Gemini API key                |
| `GEMINI_MODEL`        | ❌       | Pro model for extraction/synthesis (`gemini-3.1-pro-preview`) |
| `GEMINI_FLASH_MODEL`  | ❌       | Flash model for scoring (`gemini-3-flash-preview`) |
| `GEMINI_REQUEST_TIMEOUT_MS` | ❌ | Per Gemini request timeout (`45000`) |
| `TELEGRAM_BOT_TOKEN`  | ✅       | Telegram bot token            |
| `TELEGRAM_CHANNEL_ID` | ✅       | Target channel (`#科技脈搏`)  |
| `APIFY_API_KEY`       | ❌       | Social trending and deep article extraction (optional) |
| `APIFY_ARTICLE_ACTOR` | ❌       | Apify actor for deep article extraction (`apify/website-content-crawler`) |
| `NEWSAPI_KEY`         | ❌       | Supplemental news (optional)  |
| `MIN_BASE_SCORE_THRESHOLD` | ❌ | Cheap pre-LLM heuristic gate (`0.35`) |
| `MIN_LEXICON_SCORE` | ❌       | Domain lexicon score floor before Gemini scoring (`3.0`) |
| `MAX_SCORING_ARTICLES` | ❌      | Max articles scored per run (`24`) |
| `MAX_UNSCORED_TAIL` | ❌ | Max scoring-failed articles merged into the delivery pool (`3`; same env as Telegram unscored tail budget) |
| `MAX_EXTRACTION_ARTICLES` | ❌   | Max articles extracted per run (`8`) |
| `TRANSLATION_AGENT_ENABLED` | ❌ | Flash backfill `zh_title` / `zh_summary` when extractor misses CJK (`1`) |
| `MAX_TRANSLATION_ARTICLES` | ❌ | Cap translation calls per run (defaults to `MAX_EXTRACTION_ARTICLES`) |
| `MAX_DEEP_ARTICLES` | ❌       | Max KOL/paper deep briefs generated per run (`3`) |
| `MIN_DEEP_WORDS` | ❌          | Minimum public full-text length before deep chain runs (`800`) |
| `MAX_EARNINGS_FILINGS` | ❌      | Watchlist full pipeline per run (`8`) |
| `MAX_EARNINGS_FILINGS_BROAD` | ❌ | Non-watchlist XBRL archive per run (`30`) |
| `EARNINGS_REPORTS_ENABLED` | ❌ | Write `tech_pulse_earnings_reports` (`1`) |
| `EARNINGS_VENDOR_MODE` | ❌ | `off` \| `free` \| `paid` — Finnhub enrich (`off` default) |
| `EARNINGS_FUNDAMENTAL_MODE` | ❌ | `off` \| `free` \| `paid` — FMP ratios / cash-flow fill-in (`off` = SEC-only) |
| `FMP_API_KEY` | ❌ | **Required** when `EARNINGS_FUNDAMENTAL_MODE=free\|paid` |
| `MAX_FMP_CALLS_PER_RUN` | ❌ | FMP HTTP calls per pipeline run (`40`) |
| `FINNHUB_API_KEY` | ❌ | **Required** when `EARNINGS_VENDOR_MODE=free\|paid` |
| `FINNHUB_HTTP_TIMEOUT_SEC` | ❌ | Finnhub HTTP timeout (`10`) |
| `FINNHUB_TRANSCRIPT_TIMEOUT_SEC` | ❌ | Transcript fetch cap per filing (`15`) |
| `EARNINGS_TRANSCRIPT_MAX_TIER` | ❌ | Max watchlist tier for transcript LLM (`2`) |
| `MAX_VENDOR_CALLS_PER_RUN` | ❌ | Finnhub calls per pipeline run (`20`) |
| `MAX_SEC_API_CALLS_PER_RUN` | ❌ | SEC companyfacts calls per run (`60`) |
| `SEC_USER_AGENT` | ✅ | SEC EDGAR User-Agent (email required by SEC policy) |
| `PIPELINE_TIMEOUT_SECONDS` | ❌   | Stop new work before Cloud Run timeout (`540`) |
| `MAX_ITEMS_PER_DIGEST` | ❌      | Max items shown in Telegram digest (`6`) |
| `DIGEST_FORMAT` | ❌ | Telegram digest layout: `v1` = canonical #科技脈搏 (📡 / 🗞️ / 🧭 / 📈 / 🧠 / themed items); `v2` = experimental numbered digest (`v1` default; unknown values fall back to `v1`) |
| `DIGEST_HEADER_TIMEZONE` | ❌ | IANA timezone for digest header date/time (`Asia/Taipei` default; pipeline timestamps are UTC, header converts for display) |
| `MIN_DIGEST_ITEMS` | ❌         | Minimum digest items, filled with fallback summaries when needed (`3`) |
| `ITEM_DIGEST_THEME_MIN_SUMMARIES` | ❌ | Minimum summaries before running the synthesizer for headline / themes / narrative (`2`; set `3` to reduce synthesis cost on thin runs) |
| `MAX_SUMMARY_CHARS` | ❌        | Max chars per item structured body in Telegram digest (`340`; Telegram hard limit is 4096 per message) |
| `EXTRACTOR_MAX_INPUT_CHARS` | ❌ | Article text slice sent to extraction (`6000`) |
| `MIN_WHAT_HAPPENED_CHARS` | ❌ | If `what_happened` is shorter than this after the reviewer LLM pass, trigger one grounded extraction retry (`45`) |
| `STATE_BACKEND`        | ❌       | Persistent state backend: `auto`, `sqlite`, or `firestore` (`auto`) |
| `FIRESTORE_COLLECTION_PREFIX` | ❌ | Collection prefix for production state (`tech_pulse`) |
| `MEMORY_ENABLED`       | ❌       | Enable Firestore retrieval memory (`1`) |
| `MEMORY_BACKEND`       | ❌       | Retrieval memory backend; currently `firestore` only |
| `GEMINI_EMBEDDING_MODEL` | ❌     | Gemini embedding model (`gemini-embedding-001`) |
| `MEMORY_EMBEDDING_DIM` | ❌       | Embedding dimension stored in Firestore (`768`) |
| `MEMORY_TOP_K`         | ❌       | Similar historical items checked per summary (`3`) |
| `SEMANTIC_DUP_DISTANCE_THRESHOLD` | ❌ | Cosine distance threshold for near-duplicate detection (`0.12`) |
| `SEMANTIC_DUP_DROP_ENABLED` | ❌  | Drop semantic duplicates when `1`; rollout default is context-only (`0`) |
| `TELEGRAM_CHUNK_DELAY_MS` | ❌      | Delay between digest chunks to prevent rate limiting (`500`) |
| `SEMANTIC_PREFILTER_ENABLED` | ❌   | Enable pre-extraction semantic dedup via 7-day embedding window (`0`) |
| `SEMANTIC_PREFILTER_THRESHOLD` | ❌ | Cosine similarity threshold for pre-extraction dedup (`0.85`) |
| `DASHBOARD_REVALIDATE_URL` | ❌ | Full URL for dashboard ISR webhook, e.g. `https://<host>/api/revalidate` |
| `DASHBOARD_REVALIDATE_TOKEN` | ❌ | Shared secret; must match dashboard `REVALIDATE_TOKEN` |
| `DASHBOARD_REVALIDATE_TIMEOUT` | ❌ | HTTP timeout seconds for revalidate POST (`5`) |

Heuristic prefilter (`scoring/heuristic_filter.py`) drops articles that do not match at least one of the **AI / semiconductor / crypto** term clusters before Gemini scoring. Matched items must also include a depth marker (e.g. announced, earnings) or concrete figures (%, $, dates); see `gate:needs_depth_or_specifics` in `base_score_status` logs.

## Dashboard (Next.js)

Reader UI lives under [`dashboard/`](dashboard/). Deploy to Vercel with project root `dashboard/`; env vars in [`dashboard/.env.example`](dashboard/.env.example).

**Earnings column** (reads `tech_pulse_earnings_reports`, not `memory_items`):

| Route | Description |
|-------|-------------|
| [`/earnings`](dashboard/app/(app)/earnings/page.tsx) | Recent filings by `published_at` |
| [`/earnings/[ticker]`](dashboard/app/(app)/earnings/[ticker]/page.tsx) | Per-symbol history + same-tier peers |
| [`/earnings/report/[reportId]`](dashboard/app/(app)/earnings/report/[reportId]/page.tsx) | Full v3 deep report (`rendered_markdown_zh`) |
| [`/portfolio`](dashboard/app/(app)/portfolio/page.tsx) | Holdings, theme exposure, allocation drift vs `config/portfolio.yaml` |

**Portfolio** data lives in [`config/portfolio.yaml`](config/portfolio.yaml) (manual edit or
[`scripts/import_ibkr_portfolio.py`](scripts/import_ibkr_portfolio.py) from IBKR Flex:
`IBKR_FLEX_TOKEN`, `IBKR_FLEX_QUERY_ID`). After editing yaml, run
`python3 scripts/export_portfolio_json.py` before `npm run build` in `dashboard/`. Optional
`FINNHUB_API_KEY` on Vercel enables live quotes; otherwise the UI shows cost-basis valuation.

Homepage shows **今日財報** when filings landed today (Asia/Taipei). Finnhub keys are configured on the **pipeline** (Cloud Run), not Vercel — the dashboard only needs Firestore read access.

| Mode | Behavior |
|------|----------|
| **Basic Auth** (default when credentials set) | Whole-site HTTP Basic when `DASHBOARD_PUBLIC_READ` is unset |
| **Public read** | `DASHBOARD_PUBLIC_READ=true` — anonymous title/`zh_summary`; full `zh_body` after `/login` + signed cookie |

Provision a read-only Firestore SA: `PROJECT_ID=<gcp-project> ./scripts/setup_dashboard_sa.sh`

Portal / third-party readers: [`docs/PORTAL_CONTRACT.md`](docs/PORTAL_CONTRACT.md)

Local verification (matches CI dashboard job):

```bash
cd dashboard && npm run lint && npm run typecheck && npm run test && npm run build
```

Shared UI helpers live under `dashboard/lib/format-numbers.ts`, `login-path.ts`, and `dashboard/components/BrandMark.tsx` / `InstantCardNewsList.tsx` — see [`dashboard/README.md`](dashboard/README.md).

## Deployment

**Vercel + GCP 設定清單**（env、驗證、backfill）：[`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md).

The pipeline is packaged for container deployment. Run `python scripts/preflight.py` in
the same environment before the first production run, then start the one-shot command:

```bash
python main.py
```

### Continuous deployment (GitHub Actions → Cloud Run Job)

Pushes to `main` automatically run tests, build, and deploy the Cloud Run Job via
`.github/workflows/ci.yml`. Configure the following in the GitHub repository
settings before relying on it:

**Repository variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Example |
|----------|---------|
| `GCP_PROJECT_ID` | `my-gcp-project` |
| `GCP_REGION` | `asia-east1` |
| `ARTIFACT_REGISTRY_REPO` | `tech-pulse-images` |
| `CLOUD_RUN_SERVICE` | `tech-pulse` (Cloud Run Job name) |

**Repository secrets** (Workload Identity Federation — no JSON key needed):

| Secret | Description |
|--------|-------------|
| `WIF_PROVIDER` | Full WIF provider resource name, e.g. `projects/123/locations/global/workloadIdentityPools/github/providers/github-actions` |
| `WIF_SERVICE_ACCOUNT` | Service account email with `roles/run.developer` and `roles/artifactregistry.writer` |

The Artifact Registry repo and Cloud Run Job must already exist (the workflow updates the
existing job's image; it does not create resources). Each deploy runs `gcloud run jobs update`
with `--update-env-vars DIGEST_FORMAT=v1` so production keeps the canonical #科技脈搏 digest layout
unless you override that variable in GCP. If you prefer to deploy as a
Cloud Run Service instead of a Job, swap `gcloud run jobs update` for
`gcloud run deploy` in the workflow.

### Production state on Firestore

Local runs default to `output/dedup.sqlite`. Cloud Run uses Firestore when `STATE_BACKEND=auto`
or `STATE_BACKEND=firestore`, so the dedup state survives stateless container restarts:

```bash
gcloud services enable firestore.googleapis.com --project "$GCP_PROJECT_ID"

gcloud run jobs update "$CLOUD_RUN_SERVICE" \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --set-env-vars STATE_BACKEND=auto,FIRESTORE_COLLECTION_PREFIX=tech_pulse
```

Grant the Cloud Run runtime service account Firestore access:

```bash
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SERVICE_ACCOUNT" \
  --role="roles/datastore.user"
```

The Firestore backend writes `tech_pulse_seen_items` and `tech_pulse_saved_items`.
Configure a Firestore TTL policy on the `expires_at` field of `tech_pulse_seen_items`
to let GCP expire old dedup records automatically.

Content-hash deduplication also needs a composite Firestore index on
`tech_pulse_seen_items` for `content_hash ASC, seen_at ASC`. Deploy
`firestore.indexes.json`, or create it directly:

```bash
gcloud firestore indexes composite create \
  --project "$GCP_PROJECT_ID" \
  --collection-group tech_pulse_seen_items \
  --query-scope COLLECTION \
  --field-config field-path=content_hash,order=ascending \
  --field-config field-path=seen_at,order=ascending
```

### Firestore retrieval memory

When `MEMORY_ENABLED=1`, delivered digest items, deep briefs, and earnings outputs are archived
to `tech_pulse_memory_items` after Telegram delivery succeeds. Future runs use Firestore vector
search to find related historical items, attach a short background hint to the digest, and mark
near-duplicates. The rollout default is conservative: `SEMANTIC_DUP_DROP_ENABLED=0` archives and
searches memory without suppressing items.

Create the vector index before enabling duplicate dropping:

```bash
gcloud firestore indexes composite create \
  --project "$GCP_PROJECT_ID" \
  --collection-group tech_pulse_memory_items \
  --query-scope COLLECTION \
  --field-config field-path=embedding,vector-config='{"dimension":"768", "flat": "{}"}'
```

If the vector index is missing or still building, the pipeline logs a warning and continues
without memory search for that run.

## Troubleshooting: Telegram digest shows only one item

Each run logs a JSON line `pipeline_run_summary { ... }` with funnel counts. Compare:

| Field | Meaning |
|-------|---------|
| `articles_fetched` | RSS + merges before dedup |
| `articles_after_dedup` | Unseen URLs |
| `articles_after_scoring` | After Flash gate + threshold |
| `instant_candidates` | Length of `instant_scored_articles` passed into extraction |
| `summaries_count` | Summaries after reviewer + minimum padding + dedup claim |

Inspect `OUTPUT_DIR/summaries_<timestamp>.json` for the same run: count rows and check `score` / `score_status` / `confidence`.

**Header time** — The `📡 科技脈搏 · …` timestamp is converted from UTC to **`DIGEST_HEADER_TIMEZONE`** (default `Asia/Taipei`). Use `UTC` if you want the header to match Cloud Run’s coordinated time.

**Typical causes**

1. **Synthesis skipped** — need `summaries_count >= ITEM_DIGEST_THEME_MIN_SUMMARIES` (default `2`) and at least one deliverable scored item. With one summary you still get a items-only digest (no `🗞️` / `🧭`). Lower `ITEM_DIGEST_THEME_MIN_SUMMARIES` to `1` if you always want a headline block (extra LLM cost).
2. **Thin instant pool** — `_ensure_minimum_summaries` now pads from the merged instant list **plus** full `scored_articles` so deep-tier consumption does not starve minimum digest size when other scored URLs exist.
3. **Scoring** — most articles below `SCORE_THRESHOLD` or lexicon/heuristic prefilter.
4. **`MAX_UNSCORED_TAIL`** — scorer and formatter both read this env (default `3`); caps how many scoring-failed articles enter the delivery pool.

## Project Structure

```
tech-pulse/
├── sources/              RSS, social, earnings, IR scrapers
├── agents/               Gemini agent wrappers (extractor, synthesizer, earnings)
├── llm/                  Shared Gemini client helpers
├── scripts/              Production preflight checks
├── pipeline/             Orchestration + scheduling
├── delivery/             Telegram bot + dashboard ISR webhook
├── dashboard/            Next.js 15 web reader (Firestore)
├── docs/                 Portal contract, integration notes
├── scripts/              preflight, GDELT backfill, dashboard SA setup
└── tests/                Smoke tests + LLM-as-judge
```

See [CLAUDE.md](CLAUDE.md) for full design constraints and schema contracts. Track open work in [TODOS.md](TODOS.md); release notes in [CHANGELOG.md](CHANGELOG.md). Contributor/agent workflow: [docs/WORKFLOW.md](docs/WORKFLOW.md).
