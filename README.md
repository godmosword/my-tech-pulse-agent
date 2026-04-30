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
| `GEMINI_REQUEST_TIMEOUT_MS` | ❌ | Per Gemini request timeout (`45000`) |
| `TELEGRAM_BOT_TOKEN`  | ✅       | Telegram bot token            |
| `TELEGRAM_CHANNEL_ID` | ✅       | Target channel (`#科技脈搏`)  |
| `APIFY_API_KEY`       | ❌       | Social trending (optional)    |
| `NEWSAPI_KEY`         | ❌       | Supplemental news (optional)  |
| `MAX_SCORING_ARTICLES` | ❌      | Max articles scored per run (`24`) |
| `MAX_EXTRACTION_ARTICLES` | ❌   | Max articles extracted per run (`8`) |
| `MAX_EARNINGS_FILINGS` | ❌      | Max earnings filings processed per run (`2`) |
| `PIPELINE_TIMEOUT_SECONDS` | ❌   | Stop new work before Cloud Run timeout (`540`) |

## Deployment

The pipeline is packaged for container deployment. Run `python scripts/preflight.py` in
the same environment before the first production run, then start the one-shot command:

```bash
python -m pipeline.crew
```

### Continuous deployment (GitHub Actions → Cloud Run Job)

Pushes to `main` (when Python, Dockerfile, or relevant config files change) automatically
build and deploy the Cloud Run Job via `.github/workflows/deploy.yml`. The workflow uses
the same JSON-key auth pattern as `my-investment-ai-agent`.

Configure the following **secrets** under Settings → Secrets and variables → Actions:

| Secret | Description / where to find it |
|--------|-------------------------------|
| `GCP_PROJECT_ID` | GCP project ID, e.g. `my-tech-pulse-prod` |
| `GCP_SA_KEY` | Full JSON of a service account key with `roles/run.developer`, `roles/artifactregistry.writer`, and `roles/iam.serviceAccountUser` on the Cloud Run runtime SA. Generate with `gcloud iam service-accounts keys create key.json --iam-account=...`. |
| `GAR_REPOSITORY` | Artifact Registry repo short name, e.g. `tech-pulse-images` |
| `CLOUD_RUN_SERVICE` | Cloud Run Job name. Optional — defaults to `tech-pulse`. |

Region is hardcoded to `asia-east1` in the workflow. Edit `GCP_REGION` in
`deploy.yml` if you use a different region.

The Artifact Registry repo and Cloud Run Job must already exist; the workflow only
builds/pushes the image and updates the job. To deploy as a Cloud Run Service instead,
swap `gcloud run jobs deploy` for `gcloud run deploy` in `deploy.yml`.

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
