# tech-pulse

AI-powered tech news intelligence pipeline. Scrapes trending tech news from RSS feeds and social
platforms, runs multi-layer Gemini agent analysis, parses earnings reports from SEC EDGAR, and
delivers structured summaries to a Telegram channel (#科技脈搏).

## Quick Start

```bash
pip install -e .
cp .env.example .env   # fill in your keys
python -m pipeline.crew          # one-shot run
python -m pipeline.scheduler     # continuous 15-min polling
python scripts/preflight.py      # production config check
```

## Pipeline Overview

```
RSS / Social / SEC EDGAR
        ↓
  Gemini Pro Extractor
  → per-article structured JSON with confidence score
        ↓
  Gemini Pro Synthesizer
  → cross-article themes + daily digest narrative
        ↓
  Telegram Delivery (#科技脈搏)
```

Earnings reports follow a dedicated sub-pipeline:

```
SEC EDGAR RSS → earnings_fetcher → earnings_agent (fact_guard enforced)
             → structured earnings JSON → Telegram + investment-digest
```

## Environment Variables

| Variable              | Required | Description                   |
|-----------------------|----------|-------------------------------|
| `GEMINI_API_KEY`      | ✅       | Gemini API key                |
| `GEMINI_MODEL`        | ❌       | Pro model for extraction/synthesis (`gemini-3.1-pro-preview`) |
| `GEMINI_FLASH_MODEL`  | ❌       | Flash model for scoring (`gemini-3-flash-preview`) |
| `TELEGRAM_BOT_TOKEN`  | ✅       | Telegram bot token            |
| `TELEGRAM_CHANNEL_ID` | ✅       | Target channel (`#科技脈搏`)  |
| `APIFY_API_KEY`       | ❌       | Social trending (optional)    |
| `NEWSAPI_KEY`         | ❌       | Supplemental news (optional)  |

## Deployment

GitHub Actions runs the production pipeline every 15 minutes and deploys the generated
`docs/` artifact to GitHub Pages. Configure these repository secrets before enabling the
workflow:

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

Optional secrets: `APIFY_API_KEY`, `NEWSAPI_KEY`. Optional repository variable:
`GITHUB_PAGES_URL`.

Run `python scripts/preflight.py` locally or in a shell with the same environment before
the first production run.

## Project Structure

```
tech-pulse/
├── sources/              RSS, social, earnings, IR scrapers
├── agents/               Gemini agent wrappers (extractor, synthesizer, earnings)
├── llm/                  Shared Gemini client helpers
├── scripts/              Production preflight checks
├── pipeline/             Orchestration + scheduling
├── delivery/             Telegram bot
├── dashboard/            Future web UI
└── tests/                Smoke tests + LLM-as-judge
```

See [CLAUDE.md](CLAUDE.md) for full design constraints and schema contracts.
