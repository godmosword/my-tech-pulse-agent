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
  → theme-aware message chunking at 4096 char boundaries
```

**Smart message delivery**: Long digests are split intelligently at newline (theme) boundaries to preserve formatting. Messages stay under Telegram's 4096 character limit while maintaining MarkdownV2 escape sequences. Each chunk includes validation and configurable inter-message delays.

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
| `APIFY_API_KEY`       | ❌       | Social trending and deep article extraction (optional) |
| `APIFY_ARTICLE_ACTOR` | ❌       | Apify actor for deep article extraction (`apify/website-content-crawler`) |
| `NEWSAPI_KEY`         | ❌       | Supplemental news (optional)  |
| `MIN_BASE_SCORE_THRESHOLD` | ❌ | Cheap pre-LLM heuristic gate (`0.35`) |
| `MIN_LEXICON_SCORE` | ❌       | Domain lexicon score floor before Gemini scoring (`3.0`) |
| `MAX_SCORING_ARTICLES` | ❌      | Max articles scored per run (`24`) |
| `MAX_EXTRACTION_ARTICLES` | ❌   | Max articles extracted per run (`8`) |
| `MAX_DEEP_ARTICLES` | ❌       | Max KOL/paper deep briefs generated per run (`3`) |
| `MIN_DEEP_WORDS` | ❌          | Minimum public full-text length before deep chain runs (`800`) |
| `MAX_EARNINGS_FILINGS` | ❌      | Max earnings filings processed per run (`2`) |
| `PIPELINE_TIMEOUT_SECONDS` | ❌   | Stop new work before Cloud Run timeout (`540`) |
| `MAX_ITEMS_PER_DIGEST` | ❌      | Max items shown in Telegram digest (`6`) |
| `MIN_DIGEST_ITEMS` | ❌         | Minimum digest items, filled with fallback summaries when needed (`3`) |
| `MAX_SUMMARY_CHARS` | ❌        | Max chars per item summary in Telegram digest (`260`) |
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

## Deployment

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
existing job's image; it does not create resources). If you prefer to deploy as a
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
