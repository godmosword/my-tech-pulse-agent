# tech-pulse

AI-powered tech news intelligence pipeline. Scrapes trending tech news from RSS feeds and social
platforms, runs multi-layer Claude agent analysis, parses earnings reports from SEC EDGAR, and
delivers structured summaries to a Telegram channel (#科技脈搏).

## Quick Start

```bash
pip install -e .
cp .env.example .env   # fill in your keys
python -m pipeline.crew          # one-shot run
python -m pipeline.scheduler     # continuous 15-min polling
```

## Pipeline Overview

```
RSS / Social / SEC EDGAR
        ↓
  Extractor Agent (Layer 1)
  → per-article structured JSON with confidence score
        ↓
  Synthesizer Agent (Layer 2)
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
| `ANTHROPIC_API_KEY`   | ✅       | Claude API key                |
| `TELEGRAM_BOT_TOKEN`  | ✅       | Telegram bot token            |
| `TELEGRAM_CHANNEL_ID` | ✅       | Target channel (`#科技脈搏`)  |
| `APIFY_API_KEY`       | ❌       | Social trending (optional)    |
| `NEWSAPI_KEY`         | ❌       | Supplemental news (optional)  |

## Project Structure

```
tech-pulse/
├── sources/              RSS, social, earnings, IR scrapers
├── agents/               CrewAI agent definitions (extractor, synthesizer, earnings)
├── pipeline/             Orchestration + scheduling
├── delivery/             Telegram bot
├── dashboard/            Future web UI
└── tests/                Smoke tests + LLM-as-judge
```

See [CLAUDE.md](CLAUDE.md) for full design constraints and schema contracts.
