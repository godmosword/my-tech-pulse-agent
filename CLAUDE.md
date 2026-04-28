# tech-pulse — CLAUDE.md

## Project Overview

tech-pulse is a modular AI-powered tech news intelligence pipeline.
It scrapes trending tech news from RSS feeds and social platforms, runs multi-layer agent analysis,
parses earnings reports from official sources, and delivers structured summaries via Telegram.

## Architecture

```
sources/      → Data ingestion (RSS, social trending, SEC EDGAR)
scoring/      → Stage 0 dedup (sqlite) + Stage 1 LLM score gate (Horizon pattern)
agents/       → Multi-layer Gemini agent wrappers (Stage 2 + 3)
pipeline/     → Orchestration (crew.py, scheduler)
delivery/     → Telegram bot output
dashboard/    → (Future) Web dashboard
tests/        → Smoke tests and LLM-as-judge validation
scripts/      → Production preflight checks
```

## Full Pipeline (Four Stages)

```
Stage 0 — Ingest & Deduplicate
  Input : raw items from all sources (RSS, social, EDGAR)
  Logic : normalize URL, compute content hash, drop seen items (sqlite TTL 72h)
  Output: deduplicated item list

Stage 1 — Score & Filter  ← Horizon pattern (Thysrael/Horizon)
  Input : deduplicated items
  Logic : Gemini Flash scores each item 0–10 (relevance/novelty/depth)
          drop items below score_threshold (default 6.0)
  Output: filtered + scored item list

Stage 2 — Extractor Agent  ← Gemini Pro
  Input : single scored article
  Output: structured JSON (entity, summary, source, score, confidence)

Stage 3 — Synthesizer Agent  ← Gemini Pro
  Input : batch of Extractor outputs
  Output: cross-article themes, contradictions, daily digest narrative
```

## Earnings Sub-Pipeline (separate, not scored — always high-value)

```
SEC EDGAR RSS → earnings_fetcher → earnings_agent (fact_guard enforced)
             → structured earnings JSON → Telegram + investment-digest
```

## Running the Pipeline

```bash
# Install dependencies
pip install -e .

# Copy and fill environment variables
cp .env.example .env

# Run the full pipeline once
python -m pipeline.crew

# Run the scheduler (15-min polling)
python -m pipeline.scheduler

# Run tests
pytest tests/

# Check production secrets and deploy config
python scripts/preflight.py
```

## Production Deployment

The GitHub Pages workflow is the production runner. On schedule or manual dispatch it:

1. Installs the package.
2. Runs `python -m pipeline.crew`.
3. Uploads generated `docs/` as a Pages artifact.
4. Deploys the current report to GitHub Pages.

Required GitHub secrets:
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

Optional GitHub secrets:
- `APIFY_API_KEY`
- `NEWSAPI_KEY`

Optional GitHub variable:
- `GITHUB_PAGES_URL`

## Anti-Hallucination Rules

- `extractor_agent` system prompt must include:
  "Only summarize what is explicitly stated in the source. Do not infer or add context."
- All agent outputs include a `confidence` field: `high | medium | low`
- **fact_guard**: numeric fields in earnings JSON must be parsed directly from structured
  source data — the LLM must never calculate or infer numbers.

## Scoring Design (Horizon-Inspired)

`scoring/scorer.py` scores every item **before** it reaches any Gemini Pro agent.
Uses Gemini Flash (cheap, fast). Items below threshold never reach Gemini Pro.

Scoring prompt evaluates three dimensions:
- **Relevance** (weight 0.4): Is this meaningful tech/business news?
- **Novelty**   (weight 0.3): Is this new information, not a rehash?
- **Depth**     (weight 0.3): Does it contain specific facts?

Thresholds in `scoring/score_config.yaml`:
- `default: 6.0` — general news
- `earnings: 7.5` — stricter for financial facts
- `social_signal: 4.0` — looser (signal-only)

## Deduplication Design

`scoring/deduplicator.py` uses sqlite3 (built-in) with:
- Primary key: SHA-256 of normalized URL (tracking params stripped)
- Secondary key: SHA-256 of first 500 chars of title+content
- TTL: 72 hours (configurable via `DEDUP_TTL_HOURS`)

## Earnings JSON Contract

Every `earnings_agent` output must conform to this schema:

```json
{
  "company": "string",
  "quarter": "string (e.g. Q1 FY2026)",
  "revenue": { "actual": 0.0, "estimate": 0.0, "beat_pct": 0.0 },
  "eps":     { "actual": 0.0, "estimate": 0.0 },
  "segments": { "segment_name": 0.0 },
  "guidance_next_q": 0.0,
  "key_quotes": ["string"],
  "source": "SEC 10-Q | earnings PR | IR page",
  "confidence": "high | medium | low"
}
```

Do not change field names without coordinating with the investment-digest repo.

## Boundary with Investment Digest Repo

| Concern                    | tech-pulse     | investment-digest  |
|----------------------------|----------------|--------------------|
| Earnings facts             | ✅ Produces    | Consumes via JSON  |
| Investment signal          | ❌ Out of scope | ✅ Owns            |
| Tech news narrative        | ✅ Owns        | May reference      |
| Telegram delivery          | #科技脈搏      | #投資日報          |

Cross-tagging: when a story is relevant to both repos, emit `cross_ref: true` in the JSON.

## V1 Feature Status

- RSS news, Gemini scoring/extraction/synthesis, earnings extraction, Telegram delivery,
  and static Pages reports are in the production path.
- Social trending is signal-only in v1: it is fetched and logged when `APIFY_API_KEY` is set,
  but it is not yet merged into article scoring or digest synthesis.
- Feedback callbacks are implemented as handlers, but v1 Telegram broadcasts do not attach
  inline keyboards or run callback polling by default.

## Tech Stack

- Agent orchestration: direct Gemini API wrappers
- LLM (agents): Gemini Pro (`gemini-3.1-pro-preview`)
- LLM (scoring gate): Gemini Flash (`gemini-3-flash-preview`)
- Scheduling: APScheduler
- Deduplication: sqlite3 (built-in, TTL-based)
- RSS parsing: stdlib xml.etree + httpx
- PDF parsing: pdfplumber
- Delivery: python-telegram-bot
- Validation: Pydantic v2
- Testing: pytest + LLM-as-judge

## Reference Projects

| Project | What was borrowed |
|---------|-------------------|
| Thysrael/Horizon | Scoring rubric, cheap-model gate pattern, score_config schema |
| finaldie/auto-news | Source connector layering design |
| hrnrxb/AI-News-Aggregator-Bot | sqlite dedup pattern, TTL design |
