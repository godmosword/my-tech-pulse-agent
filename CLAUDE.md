# tech-pulse — Claude Code Project Brief

## Project Overview

**tech-pulse** is a **Deep Insight Miner** focused on AI, semiconductors, and crypto.

It is explicitly **not** a shallow news aggregator. The product value is extracting structured
arguments from long-form content such as KOL columns, Substack analyses, academic preprints,
industry deep-dives, and high-signal company filings, then synthesizing them into concise,
grounded insight briefs for the `#科技脈搏` Telegram channel.

Shallow headlines, PR releases, deal posts, price-action gossip, and generic "breakthrough"
language should be aggressively filtered before any expensive LLM call.

Current production baseline:
- One-shot Cloud Run Job entry point: `python main.py`
- Orchestration: `pipeline/crew.py`
- LLM provider: Gemini wrappers in `llm/gemini_client.py`
- State backend: `STATE_BACKEND=auto` uses sqlite locally and Firestore on Cloud Run
- KOL/source discovery: RSS/Atom feeds from `sources/source_registry.yaml` and `sources/kol_registry.yaml`
- Deep public full-text extraction: `sources/deep_scraper.py` delegates scraping to Apify only

Target vNext direction:
- Two content tiers with separate agent chains: **Deep**, **Instant**, and the separate **Earnings** path.
- Deep items produce 100-200 字中文 structured insight briefs.
- Instant items produce compact `fact / signal / risk` messages.

| Tier | Sources | Agent Chain | Output Format |
|---|---|---|---|
| **Deep** | Substack, personal blogs, academic preprints, KOL long-form | Extractor -> Reviewer -> Synthesizer | 100-200 字中文 structured insight brief |
| **Instant** | Bloomberg RSS, TechCrunch, The Verge, other news RSS | Extractor -> Reviewer | `fact / signal / risk` |
| **Earnings** | SEC EDGAR RSS and IR pages | earnings_agent with fact_guard | Structured earnings JSON |

Output is delivered via Telegram and may later be mirrored to GitHub Pages. The repo is separate
from the investment digest repo, but can emit structured JSON consumed upstream by investment digest.

## Architecture

```
main.py       -> Cloud Run Job one-shot entry point with POSIX exit codes
sources/      -> Data ingestion (RSS, KOL feeds, social signals, SEC EDGAR, IR pages)
scoring/      -> Dedup, cheap heuristic prefilter, Gemini Flash score gate
agents/       -> Multi-layer Gemini agent wrappers
pipeline/     -> One-shot orchestration (`crew.py`)
delivery/     -> Telegram output and feedback callbacks
dashboard/    -> Future web UI
tests/        -> Smoke tests, entrypoint tests, LLM-as-judge validation
scripts/      -> Production preflight checks
```

There must be no long-running in-process scheduler in this repo. Cloud Scheduler, GitHub Actions,
or another external trigger should invoke the Cloud Run Job. The container must run once and exit.

## Full Pipeline

Inspired by Horizon for score gating and dedup patterns, and auto-news for source connector layering.

```
Stage 0 — Ingest & Deduplicate
  Input : raw items from RSS, KOL feeds, social signals, and EDGAR
  Logic : normalize URL, compute content hash, drop seen items
          local dev uses sqlite; Cloud Run uses Firestore via state_store.py
  Output: deduplicated item list

Stage 1A — Heuristic Prefilter
  Input : deduplicated items
  Logic : deterministic local filtering in scoring/heuristic_filter.py
          high-signal technical terms boost base score
          low-signal terms penalize or drop before Gemini
          KOL/deep items bypass generic news prefilter to avoid false negatives
  Output: prefiltered candidates

Stage 1B — LLM Score Gate
  Input : prefiltered candidates
  Logic : Gemini Flash scores relevance, novelty, and depth
          deep/KOL items use depth-weighted scoring
          items below threshold never reach expensive agent calls
  Output: filtered + scored item list

Stage 2 — Extractor Agent
  Instant output    : ArticleSummary with entity, category, summary, sentiment, score, confidence
  Deep output       : ArgumentMap with core_thesis, evidence, assumption, counter_ignored
  Target instant output: fact / signal / risk

Stage 2.5 — Reviewer Agent
  Checks grounding, fact errors, unsupported inference, and quality.
  Reviewer is a grounding checker, not a generic rewriter.

Stage 3 — Synthesizer Agent
  Current v1 output : digest headline, themes, contradictions, narrative
  Deep output       : 100-200 字中文 InsightBrief with Insight / Tech Rationale / Implication
```

## Earnings Sub-Pipeline

```
SEC EDGAR RSS -> earnings_fetcher.py -> earnings_agent with fact_guard
              -> structured earnings JSON -> Telegram + investment digest handoff
```

Earnings are always high-value and should not be dropped by the general news scorer. Numeric fields
must come from source data; the LLM must never calculate or infer financial numbers.

## Running the Pipeline

```bash
# Install dependencies
pip install -e .

# Copy and fill environment variables
cp .env.example .env

# Run exactly once, as Cloud Run Job does
python main.py

# Run tests
pytest -q

# Check production secrets and runtime config
python scripts/preflight.py
```

Production containers must execute:

```bash
python main.py
```

`main.py` requirements:
- Return `sys.exit(0)` when the pipeline completes, including no-new-article runs.
- Return `sys.exit(1)` for unhandled critical exceptions or critical stage failures reported by `TechPulseCrew.run()`.
- Log a final summary line: `Pipeline completed. Fetched: X, Processed: Y, Delivered: Z`.
- Write logs to stdout/stderr for Cloud Logging.

## State Persistence

Cloud Run Job containers are ephemeral. Do not rely on local files for production state.

`scoring/state_store.py` is the state abstraction:
- `STATE_BACKEND=auto` chooses sqlite locally and Firestore on Cloud Run.
- `STATE_BACKEND=sqlite` is acceptable for local tests/dev only.
- `STATE_BACKEND=firestore` forces Firestore.
- Firestore collections use `FIRESTORE_COLLECTION_PREFIX`, default `tech_pulse`.

Deduplication contract:
- Primary key: SHA-256 of normalized URL with tracking parameters stripped.
- Secondary key: SHA-256 of the first 500 chars of title/content.
- TTL window: configured by `DEDUP_TTL_HOURS`.
- Firestore should use TTL on `expires_at` for production cleanup.

Feedback callback state:
- `save:{item_id}` writes to the configured state store, not directly to sqlite.
- Firestore dedup claims must use transaction blocks so concurrent Cloud Run Jobs do not process the same item twice.

## Key Design Constraints

### Scoring Design

Current v1:
- `scoring/heuristic_filter.py` performs no-cost prefiltering before Gemini.
- `sources/domain_lexicon.yaml` is the source of truth for AI, semiconductor, and crypto signals.
- `scoring/scorer.py` annotates each item with `lexicon_score` and `matched_signals`.
- `scoring/scorer.py` uses Gemini Flash as a cheap score gate.
- `agents/deep_insight_agent.py` loads `sources/domain_lexicon.yaml` and downgrades low-density deep insights.
- Runtime cap: `MAX_SCORING_ARTICLES`.
- Deep runtime cap: `MAX_DEEP_ARTICLES`.
- Deep full-text minimum: `MIN_DEEP_WORDS`.
- Heuristic threshold: `MIN_BASE_SCORE_THRESHOLD`.
- Domain lexicon floor: `MIN_LEXICON_SCORE`.
- KOL/deep items must not be accidentally dropped by shallow-news rules.

Target vNext:
- Expand `sources/domain_lexicon.yaml` with per-domain weights and source-specific overrides.
- Replace remaining broad heuristic term lists in code with configurable high/low signal domain weights.
- Keep the same two-pass shape: deterministic lexicon first, LLM scoring second.

Example target lexicon:

```yaml
semiconductor:
  high_signal: [advanced packaging, CoWoS, HBM, chiplet, EUV, GAA, backside power,
                hybrid bonding, die-to-die interconnect]
  low_signal: [new chip, performance boost, next generation, unveiled, faster]

ai:
  high_signal: [attention mechanism, KV cache, MoE, quantization, RLHF, inference latency,
                memory bandwidth, sparsity, transformer, RAG, context window]
  low_signal: [powerful AI, breakthrough, outperforms GPT, revolutionary, game-changing]

crypto:
  high_signal: [consensus mechanism, ZK proof, sequencer, data availability, MEV,
                L2 finality, rollup, blob, EIP, restaking, AVS]
  low_signal: [price prediction, bull run, altcoin, WAGMI, to the moon, passive income]
```

### Target Output Schemas

Deep tier target `ArgumentMap`:

```python
class ArgumentMap(BaseModel):
    title: str
    author: str | None
    source_name: str
    url: str
    domain: Literal["ai", "semiconductor", "crypto", "other"]
    tier: Literal["deep", "instant"]
    core_thesis: str
    evidence: list[str]
    assumption: str | None
    counter_ignored: str | None
    score: float
    confidence: Literal["high", "medium", "low"]
    item_id: str
```

Deep tier target `InsightBrief`:

```python
class InsightBrief(BaseModel):
    item_id: str
    title: str
    author: str | None
    source_name: str
    url: str
    domain: Literal["ai", "semiconductor", "crypto", "other"]
    insight: str
    tech_rationale: str
    implication: str
    word_count: int
    cross_ref: bool
    confidence: Literal["high", "medium", "low"]
```

Current MVP enforces `InsightBrief` length at 100-200 mixed Chinese characters / English tokens.

Instant tier target `ExtractorOutput`:

```python
class ExtractorOutput(BaseModel):
    title: str
    fact: str
    signal: str
    risk: str | None
    tags: list[str]
    source_name: str
    url: str
    score: float
    confidence: Literal["high", "medium", "low"]
    is_earnings: bool
    cross_ref: bool
    item_id: str
```

## Agent Prompt Rules

Deep tier extractor:
- Do not summarize.
- Map the argument structure.
- Extract evidence near-verbatim, especially numbers and technical terms.
- Identify the author's core thesis, assumptions, and ignored counterarguments.
- If the article does not engage with technical mechanisms, set `confidence="low"`.

Instant tier extractor:
- `fact` must state only explicitly written source content.
- Numbers must match source verbatim.
- `signal` may be judgment, but must name concrete entities and mechanisms.
- Unsupported causal claims must be tagged `[INFERRED]`.

Reviewer:
- Verify grounding only.
- Do not rewrite for style.
- On retry, state exactly what is missing and where to find it in the source.
- Max retry target is 1; confidence degrades to `low` after retry.

Synthesizer:
- Deep tier only.
- Output exactly three conceptual sections: Insight, Tech Rationale, Implication.
- Total brief target: 100-200 mixed Chinese characters / English technical tokens.
- Do not invent statistics not present in `ArgumentMap.evidence`.

## Anti-Hallucination Rules

- Deep tier evidence must be near-verbatim from the source.
- Instant tier `fact` fields must include only explicitly stated source content.
- Earnings numeric fields must be parsed from source data; no LLM math.
- `InsightBrief.tech_rationale` may reason from evidence but must not cite new facts.
- All agent outputs must carry `confidence`.
- Any unsupported signal must be marked `[INFERRED]`.

## Source Strategy

| Source Type | Sources | Tool | Tier | Label |
|---|---|---|---|---|
| Primary news | Bloomberg RSS, TechCrunch, The Verge, Ars, Wired | `rss_fetcher.py` | instant | `[news]` |
| KOL long-form | Substack, personal blogs, VC/strategy blogs | `rss_fetcher.py` + `deep_scraper.py` | deep | `[kol]` |
| Academic | arXiv, IACR ePrint | target RSS connectors | deep | `[paper]` |
| Earnings | SEC EDGAR RSS, IR pages | `earnings_fetcher.py`, `ir_scraper.py` | earnings | `[earnings]` |
| Social signal | X / Threads trend metadata only | `social_tracker.py` | signal only | none |

`sources/kol_registry.yaml` is the source of truth for KOL feeds. Do not hardcode KOL sources in code.

Recommended target KOL registry fields:

```yaml
kol_sources:
  - name: stratechery
    author: Ben Thompson
    url: https://stratechery.com/feed/
    tier: deep
    domain: [tech_strategy, platform, semiconductors]
    priority: 1
    enabled: true
```

## Delivery Spec

Phase 1 Telegram:
- Every run sends one ranked digest when content exists.
- Items are sorted by score descending.
- `MAX_ITEMS_PER_DIGEST` controls bundle size.
- Telegram output must use MarkdownV2 escaping for dynamic text.
- Never emit raw URLs; use `[text](url)`.
- `cross_ref: true` appends `投資日報` handoff text.

Target deep item format:

```text
🧠 *{title}*
_{author} · {source_name}_

💡 *洞見*
{insight}

⚙️ *技術底層*
{tech_rationale}

🔁 *產業影響*
{implication}

#{domain} [原文]({url})
```

Target instant item format:

```text
⭐ {score:.1f} *{title}*
📌 {fact}
💡 {signal}
⚠️ {risk}
[{source_name}]({url})
```

Inline keyboard callbacks:
- `useful:{source_name}` increments source weight.
- `save:{item_id}` writes to the configured state store.
- `block_source:{source_name}` disables the source for the next run.

Phase 2 GitHub Pages:
- Future static report generator can write `docs/{YYYY-MM-DD}.html`.
- Telegram can link to the full report via `GITHUB_PAGES_URL`.

Phase 3 Dashboard:
- Defer until multi-user access or real-time filtering is required.
- Dashboard should query existing stored outputs; it should not become a second pipeline.

## Earnings JSON Contract

Every `earnings_agent` output must conform to this schema:

```json
{
  "company": "string",
  "quarter": "string (e.g. Q1 FY2026)",
  "revenue": { "actual": 0.0, "estimate": 0.0, "beat_pct": 0.0 },
  "eps": { "actual": 0.0, "estimate": 0.0 },
  "segments": { "segment_name": 0.0 },
  "guidance_next_q": 0.0,
  "key_quotes": ["string"],
  "source": "SEC 10-Q | earnings PR | IR page",
  "confidence": "high | medium | low"
}
```

This JSON is the shared interface with the investment digest repo. Do not change field names
without coordinating with investment digest.

## Environment Variables

Required:
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

Optional:
- `APIFY_API_KEY`
- `APIFY_ARTICLE_ACTOR`
- `NEWSAPI_KEY`
- `GEMINI_MODEL`
- `GEMINI_FLASH_MODEL`
- `GEMINI_REQUEST_TIMEOUT_MS`
- `STATE_BACKEND`
- `FIRESTORE_PROJECT_ID`
- `FIRESTORE_DATABASE`
- `FIRESTORE_COLLECTION_PREFIX`
- `DEDUP_TTL_HOURS`
- `MIN_BASE_SCORE_THRESHOLD`
- `MIN_LEXICON_SCORE`
- `MAX_SCORING_ARTICLES`
- `MAX_EXTRACTION_ARTICLES`
- `MAX_DEEP_ARTICLES`
- `MIN_DEEP_WORDS`
- `MAX_EARNINGS_FILINGS`
- `MAX_ITEMS_PER_DIGEST`
- `MIN_DIGEST_ITEMS`
- `MAX_SUMMARY_CHARS`
- `PIPELINE_TIMEOUT_SECONDS`
- `GITHUB_PAGES_URL`

## Tech Stack

| Layer | Current Choice |
|---|---|
| Runtime | Cloud Run Job, one invocation per run |
| Entrypoint | `main.py` |
| Orchestration | Direct Python orchestration in `pipeline/crew.py` |
| LLM | Gemini API wrappers |
| Score gate | Gemini Flash plus deterministic heuristic prefilter |
| Persistent state | Firestore in Cloud Run, sqlite fallback for local/dev |
| RSS parsing | stdlib `xml.etree` + `httpx` |
| PDF parsing | `pdfplumber` |
| Delivery | `python-telegram-bot` |
| Validation | Pydantic v2 |
| Testing | pytest + LLM-as-judge |

Do not reintroduce APScheduler or an in-container daemon. Scheduling belongs outside the container.

## Implementation Order

Current production hardening priority:

1. Keep `main.py` as the only production entrypoint.
2. Keep Firestore state healthy for dedup and saved items.
3. Expand domain/tier classification without breaking current news/KOL flow.
4. Expand `sources/domain_lexicon.yaml` and move remaining hardcoded heuristic terms into config.
5. Add true deep-tier full-text fetching for KOL/academic sources.
6. Implement target `ArgumentMap` and `InsightBrief` schemas.
7. Make reviewer tier-aware.
8. Update Telegram formatter for separate deep vs instant output.
9. Add GitHub Pages static report only after Telegram quality is stable.
10. Defer dashboard until there is a clear multi-user need.

## Boundary with Investment Digest Repo

| Concern | tech-pulse | investment-digest |
|---|---|---|
| Earnings facts | Produces | Consumes via JSON |
| Investment signal / trade thesis | Out of scope | Owns |
| Tech mechanism analysis | Owns | May reference |
| Telegram delivery | `#科技脈搏` | `#投資日報` |

Cross-tagging rule: when a story is relevant to both repos, emit `cross_ref: true`.
Investment digest may consume the structured JSON, but tech-pulse should not duplicate
investment recommendations.

## Reference Projects

| Project | What to borrow |
|---|---|
| Thysrael/Horizon | Scoring rubric, cheap-model gate, config schema, dedup pattern |
| finaldie/auto-news | Source connector layering |
| hrnrxb/AI-News-Aggregator-Bot | sqlite dedup and Telegram delivery patterns |
| CrewAI news-agent examples | Agent role definitions only; do not migrate orchestration without a deliberate design change |

Key architectural insight from Horizon: run a cheap fast-model score gate before expensive agent calls.
Only items scoring above threshold should reach deep extraction or synthesis.

## IDE Development Guidelines

Use these rules for Claude Code, Cursor, and other IDE agents:

1. Treat tech-pulse as a Deep Insight Miner, not a news aggregator.
2. Preserve the one-shot Cloud Run Job model. Do not add daemon loops or in-process scheduling.
3. Keep ingestion, scoring, agents, delivery, and state storage independently testable.
4. Prefer Pydantic models for agent I/O.
5. Never send shallow low-signal items to expensive LLM stages.
6. Never skip reviewer checks for high-scoring items.
7. Do not use X/Twitter as a content source; social is trend signal only.
8. Do not write generic summaries starting with "The article discusses...".
9. Do not hardcode source/domain policy once a YAML registry exists.
10. Logs should include useful run/item context: stage, score, source, confidence, and failure reason.
11. Default shipping path is direct `main`: do not open PRs unless the user explicitly asks. For production fixes, run tests, commit on `main`, and push to `origin/main`.
12. CI and Cloud Run deployment live in one GitHub Actions workflow; tests must pass before the deploy job runs.
