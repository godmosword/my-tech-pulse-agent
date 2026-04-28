# tech-pulse — CLAUDE.md

## Project Overview

tech-pulse is a modular AI-powered tech news intelligence pipeline.
It scrapes trending tech news from RSS feeds and social platforms, runs multi-layer agent analysis,
parses earnings reports from official sources, and delivers structured summaries via Telegram.

## Architecture

```
sources/      → Data ingestion (RSS, social trending, SEC EDGAR)
scoring/      → Stage 0 dedup (sqlite) + Stage 1 LLM score gate (Horizon pattern)
agents/       → Multi-layer CrewAI agent pipeline (Stage 2 + 3)
pipeline/     → Orchestration (crew.py, scheduler)
delivery/     → Telegram bot output
dashboard/    → (Future) Web dashboard
tests/        → Smoke tests and LLM-as-judge validation
```

## Full Pipeline (Four Stages)

```
Stage 0 — Ingest & Deduplicate
  Input : raw items from all sources (RSS, social, EDGAR)
  Logic : normalize URL, compute content hash, drop seen items (sqlite TTL 72h)
  Output: deduplicated item list

Stage 1 — Score & Filter  ← Horizon pattern (Thysrael/Horizon)
  Input : deduplicated items
  Logic : Claude Haiku scores each item 0–10 (relevance/novelty/depth)
          drop items below score_threshold (default 6.0)
  Output: filtered + scored item list

Stage 2 — Extractor Agent  ← CrewAI Layer 1 (Sonnet)
  Input : single scored article
  Output: structured JSON (entity, summary, source, score, confidence)

Stage 3 — Synthesizer Agent  ← CrewAI Layer 2 (Sonnet)
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
```

## Anti-Hallucination Rules

- `extractor_agent` system prompt must include:
  "Only summarize what is explicitly stated in the source. Do not infer or add context."
- All agent outputs include a `confidence` field: `high | medium | low`
- **fact_guard**: numeric fields in earnings JSON must be parsed directly from structured
  source data — the LLM must never calculate or infer numbers.

## Scoring Design (Horizon-Inspired)

`scoring/scorer.py` scores every item **before** it reaches any CrewAI agent.
Uses Claude Haiku (cheap, fast). Items below threshold never reach Sonnet.

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

## Tech Stack

- Agent orchestration: CrewAI
- LLM (agents): Claude API (`claude-sonnet-4-20250514`)
- LLM (scoring gate): Claude Haiku (`claude-haiku-4-5-20251001`)
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
