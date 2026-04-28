# tech-pulse — CLAUDE.md

## Project Overview

tech-pulse is a modular AI-powered tech news intelligence pipeline.
It scrapes trending tech news from RSS feeds and social platforms, runs multi-layer agent analysis,
parses earnings reports from official sources, and delivers structured summaries via Telegram.

## Architecture

```
sources/      → Data ingestion (RSS, social trending, SEC EDGAR)
agents/       → Multi-layer CrewAI agent pipeline
pipeline/     → Orchestration (crew.py, scheduler)
delivery/     → Telegram bot output
dashboard/    → (Future) Web dashboard
tests/        → Smoke tests and LLM-as-judge validation
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
- LLM: Claude API (`claude-sonnet-4-20250514`)
- Scheduling: APScheduler
- RSS parsing: feedparser
- PDF parsing: pdfplumber
- Delivery: python-telegram-bot
- Validation: Pydantic v2
- Testing: pytest + LLM-as-judge
