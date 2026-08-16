# tech-pulse

AI-powered tech news intelligence pipeline. Scrapes trending tech news from RSS feeds and social
platforms, runs multi-layer Gemini agent analysis, parses earnings reports from SEC EDGAR, and
delivers structured summaries to a Telegram channel (#科技脈搏).

## Quick Start

```bash
pip install -e .
cp .env.example .env   # fill in your keys
python main.py                   # one pipeline run (writes dashboard/data JSON)
python scripts/preflight.py      # production config check
```

Local setup (`.env`, Dashboard): [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md).

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
  dashboard/data JSON archive + Vercel rebuild
  → Next.js reader at dashboard/ (Vercel)
```

**Smart message delivery**: Long digests are split at newline (theme) boundaries when possible. Messages stay under Telegram's 4096 character limit with **HTML** `parse_mode` (dynamic text is escaped in `message_formatter.py`). Each chunk includes boundary validation and configurable inter-message delays (`TELEGRAM_CHUNK_DELAY_MS`).

**Web dashboard**: [`dashboard/README.md`](dashboard/README.md) reads `dashboard/data/memory_items.json`. The scheduled GitHub Action commits those files so Vercel rebuilds; ISR webhook is optional.

Earnings reports follow a dedicated sub-pipeline (`earnings_v3` in
`dashboard/data/earnings/`). SEC XBRL is the source of truth for **actual**
numbers; Finnhub supplies consensus, calendar, quote, and transcripts when enabled.

```
SEC EDGAR RSS → XBRL headline facts → narrative (8-K text)
             → Finnhub estimates/quote/calendar (optional)
             → scorecard (basis-aligned surprise) → guidance/segments/transcript
             → analyzer + conclusion → six-section Markdown
             → JSON + Telegram + Dashboard /earnings/report/{id}
```

See [`docs/EARNINGS_PORTAL.md`](docs/EARNINGS_PORTAL.md),
[`docs/EARNINGS_API_EVALUATION.md`](docs/EARNINGS_API_EVALUATION.md), and
[`docs/EARNINGS_ENV.md`](docs/EARNINGS_ENV.md) (API keys & env for v3). Vendor
enrichment (Finnhub / FMP) stays `off` by default — stage it with the phased
go/no-go runbook in [`docs/VENDOR_ENABLEMENT.md`](docs/VENDOR_ENABLEMENT.md),
verified via the additive `earnings_vendor_enriched_count` /
`earnings_fundamental_enriched_count` metrics in `pipeline_run_summary`.

## Environment Variables

| Variable              | Required | Description                   |
|-----------------------|----------|-------------------------------|
| `OPENAI_API_KEY`      | ✅       | OpenAI API key                |
| `OPENAI_MODEL`        | ❌       | Heavy path (`gpt-5.6-luna`, `reasoning.mode=pro`) |
| `OPENAI_FLASH_MODEL`  | ❌       | Scoring / zh backfill (`gpt-5.6-luna`, `effort=none`) |
| `OPENAI_EMBEDDING_MODEL` | ❌    | Embeddings (`text-embedding-3-small`) |
| `OPENAI_REQUEST_TIMEOUT_MS` | ❌ | Per OpenAI request timeout (`45000`) |
| `APIFY_API_KEY`       | ❌       | Social trending and deep article extraction (optional) |
| `APIFY_ARTICLE_ACTOR` | ❌       | Apify actor for deep article extraction (`apify/website-content-crawler`) |
| `NEWSAPI_KEY`         | ❌       | Supplemental news (optional)  |
| `MIN_BASE_SCORE_THRESHOLD` | ❌ | Cheap pre-LLM heuristic gate (`0.35`) |
| `MIN_LEXICON_SCORE` | ❌       | Domain lexicon score floor before Gemini scoring (`3.0`) |
| `MAX_SCORING_ARTICLES` | ❌      | Max articles scored per run (`24`) |
| `SCORE_THRESHOLD` | ❌ | Default Gemini score gate for the digest (falls back to `signal_config.yaml`) |
| `SCORE_THRESHOLD_<TYPE>` | ❌ | Per-type override, e.g. `SCORE_THRESHOLD_KOL`; unset/invalid falls back to `SCORE_THRESHOLD` |
| `MAX_UNSCORED_TAIL` | ❌ | Max scoring-failed articles merged into the delivery pool (`3`; same env as Telegram unscored tail budget) |
| `MAX_EXTRACTION_ARTICLES` | ❌   | Max articles extracted per run (`8`) |
| `TRANSLATION_AGENT_ENABLED` | ❌ | Flash backfill `zh_title` / `zh_summary` when extractor misses CJK (`1`) |
| `MAX_TRANSLATION_ARTICLES` | ❌ | Cap translation calls per run (defaults to `MAX_EXTRACTION_ARTICLES`) |
| `MAX_DEEP_ARTICLES` | ❌       | Max KOL/paper deep briefs generated per run (`3`) |
| `MIN_DEEP_WORDS` | ❌          | Minimum public full-text length before deep chain runs (`800`) |
| `MAX_EARNINGS_FILINGS` | ❌      | Watchlist full pipeline per run (`8`) |
| `MAX_EARNINGS_FILINGS_BROAD` | ❌ | Non-watchlist XBRL archive per run (`30`) |
| `EARNINGS_REPORTS_ENABLED` | ❌ | Write `dashboard/data/earnings/` (`1`) |
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
| `PIPELINE_TIMEOUT_SECONDS` | ❌   | Stop new work before the GitHub Actions job timeout (`540`) |
| `MAX_ITEMS_PER_DIGEST` | ❌      | Max items shown in Telegram digest (`6`) |
| `DIGEST_FORMAT` | ❌ | Telegram digest layout: `v1` = canonical #科技脈搏 (📡 / 🗞️ / 🧭 / 📈 / 🧠 / themed items); `v2` = experimental numbered digest (`v1` default; unknown values fall back to `v1`) |
| `DIGEST_HEADER_TIMEZONE` | ❌ | IANA timezone for digest header date/time (`Asia/Taipei` default; pipeline timestamps are UTC, header converts for display) |
| `MIN_DIGEST_ITEMS` | ❌         | Minimum digest items, filled with fallback summaries when needed (`3`) |
| `ITEM_DIGEST_THEME_MIN_SUMMARIES` | ❌ | Minimum summaries before running the synthesizer for headline / themes / narrative (`2`; set `3` to reduce synthesis cost on thin runs) |
| `MAX_SUMMARY_CHARS` | ❌        | Max chars per item structured body in Telegram digest (`340`; Telegram hard limit is 4096 per message) |
| `EXTRACTOR_MAX_INPUT_CHARS` | ❌ | Article text slice sent to extraction (`6000`) |
| `MIN_WHAT_HAPPENED_CHARS` | ❌ | If `what_happened` is shorter than this after the reviewer LLM pass, trigger one grounded extraction retry (`45`) |
| `STATE_BACKEND`        | ❌       | Dedup backend (`sqlite`) |
| `STATE_SQLITE_PATH`    | ❌       | Dedup / embedding sqlite path (`state/dedup.sqlite`) |
| `MEMORY_ENABLED`       | ❌       | Enable retrieval memory (`1`) |
| `MEMORY_BACKEND`       | ❌       | Retrieval memory backend (`json`) |
| `DASHBOARD_DATA_DIR`   | ❌       | JSON snapshot directory (`dashboard/data`) |
| `JSON_RETENTION_DAYS`  | ❌       | Memory / digest retention window (`90`) |
| `MEMORY_EMBEDDING_DIM` | ❌       | Embedding dimension stored in sqlite (`768`) |
| `MEMORY_TOP_K`         | ❌       | Similar historical items checked per summary (`3`) |
| `SEMANTIC_DUP_DISTANCE_THRESHOLD` | ❌ | Cosine distance threshold for near-duplicate detection (`0.12`) |
| `SEMANTIC_DUP_DROP_ENABLED` | ❌  | Drop semantic duplicates when `1`; rollout default is context-only (`0`) |
| `SEMANTIC_DUP_SHADOW_LOG` | ❌ | Log per-candidate "would-drop" decisions during the shadow rollout (`0`); see [`docs/SEMANTIC_DEDUP_ROLLOUT.md`](docs/SEMANTIC_DEDUP_ROLLOUT.md) |
| `TELEGRAM_CHUNK_DELAY_MS` | ❌      | Delay between digest chunks to prevent rate limiting (`500`) |
| `SEMANTIC_PREFILTER_ENABLED` | ❌   | Enable pre-extraction semantic dedup via 7-day embedding window (`0`) |
| `SEMANTIC_PREFILTER_THRESHOLD` | ❌ | Cosine similarity threshold for pre-extraction dedup (`0.85`) |
| `DASHBOARD_REVALIDATE_URL` | ❌ | Full URL for dashboard ISR webhook, e.g. `https://<host>/api/revalidate` |
| `DASHBOARD_REVALIDATE_TOKEN` | ❌ | Shared secret; must match dashboard `REVALIDATE_TOKEN` |
| `DASHBOARD_REVALIDATE_TIMEOUT` | ❌ | HTTP timeout seconds for revalidate POST (`5`) |

Heuristic prefilter (`scoring/heuristic_filter.py`) drops articles that do not match at least one of the **AI / semiconductor / crypto** term clusters before Gemini scoring. Matched items must also include a depth marker (e.g. announced, earnings) or concrete figures (%, $, dates); see `gate:needs_depth_or_specifics` in `base_score_status` logs.

## Dashboard (Next.js)

Reader UI lives under [`dashboard/`](dashboard/). Deploy to Vercel with project root `dashboard/`; env vars in [`dashboard/.env.example`](dashboard/.env.example).

**Earnings column** (reads `dashboard/data/earnings/`, not `memory_items.json`):

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

Homepage shows **今日財報** when filings landed today (Asia/Taipei). Finnhub keys are configured on the **pipeline** (GitHub Actions secrets), not Vercel — the dashboard reads committed JSON.

| Mode | Behavior |
|------|----------|
| **Basic Auth** (default when credentials set) | Whole-site HTTP Basic when `DASHBOARD_PUBLIC_READ` is unset |
| **Public read** | `DASHBOARD_PUBLIC_READ=true` — anonymous title/`zh_summary`; full `zh_body` after `/login` + signed cookie |

Portal / third-party readers: [`docs/PORTAL_CONTRACT.md`](docs/PORTAL_CONTRACT.md)

Local verification (matches CI dashboard job):

```bash
cd dashboard && npm run lint && npm run typecheck && npm run test && npm run build
```

Shared UI helpers live under `dashboard/lib/format-numbers.ts`, `login-path.ts`, and `dashboard/components/BrandMark.tsx` / `InstantCardNewsList.tsx` — see [`dashboard/README.md`](dashboard/README.md).

## Deployment

**Vercel + GitHub Actions 設定清單**：[`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md).
許多功能以 shadow / 預設 off 上線；待啟用旗標見 [`docs/ENABLEMENT_CHECKLIST.md`](docs/ENABLEMENT_CHECKLIST.md)。

```bash
python scripts/preflight.py
python main.py
```

### GitHub Actions

兩支自維 workflow，地圖見 [`docs/SCHEDULED_RUNS.md`](docs/SCHEDULED_RUNS.md)。

- **CI**（`.github/workflows/ci.yml`）：`main` push 跑 lint／typecheck／tests。只改 `dashboard/data/**`、`state/**`、`backtest/results/**` 的 commit 略過。
- **日更**（`.github/workflows/schedule.yml`）：23:20 UTC（07:20 台北）跑 `python main.py`，有變更才 commit JSON。`PIPELINE_SCHEDULE_ENABLED=true` 才跑 cron；手動 `workflow_dispatch` 不受限。

**日更必備 secrets**：`OPENAI_API_KEY`、`SEC_USER_AGENT`。NewsAPI／Apify 有 key 但預設關；Finnhub／FMP／FRED 未設。

### JSON memory and sqlite state

When `MEMORY_ENABLED=1`, delivered items are archived to `dashboard/data/memory_items.json`
(90-day window, no embeddings). Semantic search uses vectors in `state/dedup.sqlite`.
`SEMANTIC_DUP_DROP_ENABLED` stays `0` by default.

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

**Header time** — The `📡 科技脈搏 · …` timestamp is converted from UTC to **`DIGEST_HEADER_TIMEZONE`** (default `Asia/Taipei`). Use `UTC` if you want the header to match pipeline UTC.

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
├── dashboard/            Next.js 15 web reader (JSON snapshots)
├── docs/                 Portal contract, integration notes
├── scripts/              preflight, backfill, invest brief
└── tests/                Smoke tests + LLM-as-judge
```

See [CLAUDE.md](CLAUDE.md) for full design constraints and schema contracts. Track open work in [TODOS.md](TODOS.md); release notes in [CHANGELOG.md](CHANGELOG.md). Contributor/agent workflow: [docs/WORKFLOW.md](docs/WORKFLOW.md). Agent 編排：`docs/AGENT-WORKFLOW.md` · Domain：`docs/AGENT-DOMAIN.md`（Cursor：`/agent-plan`、`/agent-action`）。
