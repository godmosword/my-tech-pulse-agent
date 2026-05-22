# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Portal Earnings API（Slice 2）**：`GET /api/v1/earnings/upcoming`、`/{symbol}/insight`、`/watchlist`；Finnhub 行事曆 + Firestore fallback；`config/earnings_watchlist.yaml` 併入 Q-Silicon mega-cap；`scripts/export_earnings_watchlist_json.py`。
- **Portal News API（Slice 1）**：`GET /api/v1/news/digest|deep|deep/{id}|themes`（`dashboard/lib/news-api.ts`），對齊 Q-Silicon `api_routers/news.py`；digest 含 `summary` 供 `TECH_PULSE_URL`。
- **Translation Agent**（`agents/translation_agent.py`）：Extractor 未產出含 CJK 的 `zh_title` / `zh_summary` 時，以 Gemini Flash 補繁中標題與兩句摘要；`pipeline_run_summary.translation_filled_count`；`TRANSLATION_AGENT_ENABLED`（預設 `1`）。
- [`docs/EARNINGS_ENV.md`](docs/EARNINGS_ENV.md) — 財報 v3 Pipeline / Dashboard 環境變數與 API key 對照表。

### Docs
- `README.md`、`TODOS.md`、`dashboard/README.md` 同步財報深度報告 v3（Finnhub、六段報告、待辦）。
- [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md) — 本機指令：`main.py`、`backfill_zh_fields.py`、Dashboard、`setup_dashboard_sa.sh`、驗證清單。

## [0.2.1] — 2026-05-22

### Added
- **財報深度報告 v3（完整）**：Finnhub 共識/日曆/股價/逐字稿；`scorecard_builder`（GAAP vs Non-GAAP 對齊，Mixed 不計 surprise）；六段 Markdown `rendered_markdown_zh`（Scorecard、指引/CapEx、分部、電話會議、財務體質、牛熊結論）。
- **Pipeline agents**：`guidance_extractor`、`segment_extractor`、`financial_health_builder`、`transcript_agent`、`conclusion_agent`、`earnings_v3_enrich`。
- **Dashboard 財報**：`/earnings/report/[reportId]`、首頁「今日財報」、`/earnings` 深度報告連結、同 Tier 橫向比較；`GET /api/v1/earnings/ai-infra`；Firestore v2→v3 adapter。
- **財報雷達 S3–S7**：`EarningsNarrativeExtractor` + `EarningsAnalyzer`；`earnings_fact_guard` v2；Telegram `format_earnings_v2`；`VendorEarningsProvider`（預設 `EARNINGS_VENDOR_MODE=off`）；`pipeline_run_summary` earnings 指標；[`docs/EARNINGS_PORTAL.md`](docs/EARNINGS_PORTAL.md)、[`docs/EARNINGS_API_EVALUATION.md`](docs/EARNINGS_API_EVALUATION.md)。
- **財報 API（S6）**：`GET /api/v1/earnings/calendar`、`GET /api/v1/earnings/report/{reportId}`。
- **財報雷達（首期）**：SEC XBRL 主數字、`config/earnings_watchlist.yaml`、`tech_pulse_earnings_reports`、Dashboard [`/earnings`](/earnings) 與 `GET /api/v1/earnings`。
- **部署設定清單**：[`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md) — Vercel / GCP Production / Staging / 驗證與 backfill 步驟。
- **Staging 語意 prefilter**：`TECH_PULSE_ENV=staging` 自動啟用語意去重；`pipeline_run_summary` 新增 `semantic_prefilter_dropped` / `newsapi_fetched`；見 [`docs/STAGING.md`](docs/STAGING.md)。
- **NewsAPI 取料**：`sources/newsapi_fetcher.py` 在設定 `NEWSAPI_KEY` 時併入 RSS 流程。
- **Digest 快照**：`scoring/digest_store.py` 寫入 `tech_pulse_digests`；Dashboard `resolveDigestView()` 優先採用快照。
- **繁中 backfill**：[`scripts/backfill_zh_fields.py`](scripts/backfill_zh_fields.py) + [`llm/zh_backfill.py`](llm/zh_backfill.py)（Flash 輕量 JSON，只寫 `zh_title` / `zh_summary` / `hook`）；[`scripts/local_post_deploy_verify.sh`](scripts/local_post_deploy_verify.sh) 一鍵驗證 API、revalidate、backfill。
- **開發流程**：[`docs/WORKFLOW.md`](docs/WORKFLOW.md) 與 [`.cursor/rules/workflow.mdc`](.cursor/rules/workflow.mdc) — 段落完成直接 push `main` 並同步 CHANGELOG/TODOS；pipeline 路徑改動須先經維護者確認。
- **Heuristic edge tests**：[`tests/test_heuristic_filter.py`](tests/test_heuristic_filter.py) 覆蓋主題白名單、促銷/學術/薄稿、複合品質閘與歧義詞誤命中（`arm`/`sol`/`near`/`agent`）。

### Changed
- **財報 pipeline**：watchlist 路徑改為 XBRL → narrative → analyzer → fact_guard v2；Telegram 送 `EarningsReport`（v2 版型）；`scripts/backfill_earnings.py --with-llm` 同步新路徑。
- **Heuristic prefilter**（[`scoring/heuristic_filter.py`](scoring/heuristic_filter.py)）：主題命中後須有 `depth_markers` 或具體數字才進 Gemini；`reason` 新增 `gate:needs_depth_or_specifics`；收緊易誤命中詞彙。
- **Dashboard Archive**：`displayTitle()` 在 `zh_title` 過短或等同 `entity` 時改顯示英文 `title`；歸檔列表精簡 kicker（快訊不再每行 `Dispatch`）、有 `zh_summary` 時顯示副標一行。
- **Dashboard 首頁／內文**：`displayTitle()` 在缺 `zh_title` 時改以 `zh_summary` 首句作中文標題；內文頁固定呈現「中文標題／中文摘要／英文摘要」；「今日熱門代號」可點擊並以 `/archive?ticker=` 篩選相關文章。
- **繁中標題資料鏈**：extractor／`memory_store` 在缺 `zh_title` 時從 `zh_summary`／`zh_body`／`hook` 自動衍生；dashboard 讀取 `hook` 並僅在含漢字時採用繁中 fallback（避免英文 fallback 誤當標題）。
- **Dashboard REST `/api/v1`**：`items`、`items/{id}`、`digest/today`、`tickers`、`archive/facets`、`health`；`API_READ_TOKEN` Bearer 授權。
- **Social trending 接線**：Apify 熱門 hashtag 提升 `lexicon_score`（`SOCIAL_TRENDING_LEXICON_BOOST`），影響 Flash 打分候選排序。
- **財報 Telegram**：`schema_version=earnings_v3` 時送精簡 Scorecard + 結論摘要；超長自動 chunk。
- **ISR**：pipeline revalidate 預設路徑含 `/earnings`。
- **Dashboard 排版**：UI 字級（`text-kicker` / `text-meta`）加大；dark mode 主文字與次要色提亮。

### Fixed
- **財報 memory**：`archive_earnings_report` 實作誤放在 `MemoryService` Protocol，導致 `backfill_earnings` 與 production pipeline 寫入 memory 時 `AttributeError`；已移至 `FirestoreMemoryService`。
- **Dashboard 財報 API**：`/api/v1/earnings/report/[reportId]` 動態 route 改為與 `items/[id]` 相同 auth 模式（修正 Vercel build）。
- **Dashboard `/earnings/[ticker]`**：依 ticker 篩選時不再使用需複合索引的 `where + orderBy` 查詢；`metricBadge` 略過非數值指標。

### Added (ops / backfill)
- **Backfill**：先批次讀取 Firestore（避免 stream 逾時）；覆寫缺 CJK 的 `zh_*`；Pro 全量 extractor 改為 Flash zh-only，避免 JSON 截斷導致 `updated=0`。

### Ops
- **Production 維運**：Vercel `REVALIDATE_TOKEN` 與 Cloud Run `DASHBOARD_REVALIDATE_*` 對齊。
- **財報雷達資料**：`backfill_earnings`（2026-04-01〜05-21）寫入 production `tech_pulse_earnings_reports`（watchlist 19 筆 XBRL 報告）；Dashboard `/earnings` 不再空列表。

## [0.2.0] — 2026-05-19

### Added
- **Dashboard** (`dashboard/`): Next.js 15 web reader for `tech_pulse_memory_items` — Today (`/`)、Archive (`/archive`)、item detail (`/item/[id]`). Editorial layout (paper / serif / kicker), bilingual cards, facet sidebar, manual light/dark/system theme. TypeScript port of digest grouping in `lib/digest.ts` (theme tables, score badges, deep↔instant dedupe) aligned with `delivery/message_formatter.py`.
- **Public read mode**: `DASHBOARD_PUBLIC_READ` exposes title + `zh_summary` (or truncated English) to anonymous visitors; full `zh_body` behind `/login` + signed cookie (`DASHBOARD_SESSION_SECRET`). SEO via `sitemap.xml` / `robots.txt` without leaking full `summary` in HTML. See [`dashboard/README.md`](dashboard/README.md).
- **Pipeline → Dashboard ISR**: `delivery/revalidate.py` POSTs to `/api/revalidate` after delivery when `DASHBOARD_REVALIDATE_URL` + `DASHBOARD_REVALIDATE_TOKEN` are set; `scripts/setup_dashboard_sa.sh` provisions a read-only Firestore SA for Vercel.
- **繁中欄位**: Pipeline writes additive `zh_summary` / `zh_body` on memory archive; dashboard and Portal contract document the fields ([`docs/PORTAL_CONTRACT.md`](docs/PORTAL_CONTRACT.md)).
- **RSS sources**: Additional feeds in `sources/source_registry.yaml`; KOL registry tweaks.
- **Tests**: `test_dashboard_revalidate.py`, `test_zh_field_handling.py`, `test_extractor_quality_gate.py`, `test_regression_lenny_misclassification.py`, expanded formatter/smoke coverage for HTML digests.

### Changed
- **Telegram delivery**: Digest and deep cards use **`parse_mode=HTML`** (was MarkdownV2). `message_formatter.py` escapes dynamic text; `zh_summary` surfaces as card lead where present.
- **Digest formatter (v1)**: De-dupe deep insights from instant theme sections; softer score/confidence badges; cleaner meta lines (aligned with dashboard display).
- **Heuristic prefilter**: Topic whitelist — articles must hit at least one of AI / semiconductor / crypto term clusters before Gemini scoring (`scoring/heuristic_filter.py`).
- **Chinese quality**: Softer extractor gate for zh fields; drop mechanical `zh_body` from English-summary fallback (dashboard falls back to English `summary` when `zh_body` empty).
- **Web reader UX**: Scores hidden on public dashboard cards; standalone login route; `/api/revalidate` excluded from Basic Auth middleware.

### Fixed
- **Empty digest**: Fallback path when instant pool is thin after scoring/dedup.
- **KOL theme guard**: Reject deep briefs outside allowed theme set (`test_kol_allowed_themes.py`).
- **Dashboard auth**: Non-ASCII removed from `WWW-Authenticate` realm; logout route restores `Request` param for redirect URL.
- **Extractor tests**: Prompt null-assertion wording aligned with current extractor instructions.

## [0.1.4] — 2026-05-09

### Fixed
- **Digest header clock**: `📡 科技脈搏 · …` / v2 header times use **`DIGEST_HEADER_TIMEZONE`** (default `Asia/Taipei`) instead of formatting UTC as if it were local wall clock.

### Changed
- **`MAX_UNSCORED_TAIL`**: Scorer default matches Telegram formatter (`3`, was `1`) so ops expectations align when scoring fails for multiple articles.
- **Minimum digest padding**: `_ensure_minimum_summaries` pulls fallback headlines from the merged instant pool **and** full `scored_articles` when the instant shortlist is too thin (still skips URLs already extracted).

## [0.1.3] — 2026-05-09

### Fixed
- **Telegram `📈 市場含義` vs 開頭敘事**：`SynthesizerAgent.build_market_takeaway` 優先使用 narrative **第二段**（並以句號／問號等做句子邊界截斷），避免與第一段 `narrative_excerpt` 重複或在字元 180 處硬切；單段 narrative 時改為用主題名串接。`message_formatter` 若偵測 `market_takeaway` 為 `narrative_excerpt` 前綴則略過「市場含義」區塊，雙重避免重複。

### Changed
- **`DIGEST_FORMAT`**: Module constants `CANONICAL_DIGEST_FORMAT` / `EXPERIMENTAL_DIGEST_FORMAT`; unrecognized values fall back to v1 at runtime. `scripts/preflight.py` warns on `v2` or unknown layout and prepends repo root to `sys.path` so `python scripts/preflight.py` runs from project root. README + regression tests for v1 fallback / v2 opt-in. Docker image defaults `ENV DIGEST_FORMAT=v1`; CI deploy passes `--update-env-vars DIGEST_FORMAT=v1` to Cloud Run Job.
- **Digest synthesis gate**: Default `ITEM_DIGEST_THEME_MIN_SUMMARIES` is **2** (was 3). Runs with only two extracted summaries still produce headline / themes / narrative; thin RSS windows no longer drop straight to “items-only” Telegram. Set env to `3` if you prefer to skip synthesis unless there are three items. Observability: log line when synthesis is skipped (`Skipping digest synthesis: …`).
- **`pipeline_run_summary`**: Includes RSS/scoring funnel (`articles_fetched`, `articles_after_dedup`, `articles_after_scoring`, `instant_candidates`) so empty runs are obvious in one JSON log line.
- **Telegram**: Items digest increments `delivery_attempted` only when there is deliverable content (`_has_deliverable_item_signal`). Skipped sends log `Telegram items digest skipped: nothing deliverable…` instead of misleading `attempted=1 succeeded=0` with no message.
- **Firestore**: Queries use `FieldFilter` (`filter=` keyword) to silence `google-cloud-firestore` deprecation warnings on Cloud Run.
- **EDGAR earnings RSS**: Strip BOM / whitespace before XML parse; on `ParseError` log response length and a short safe head for debugging (empty body, HTML error pages, etc.).

## [2026-05-06]

### Fixed
- **Gemini JSON robustness**: Strip prose preamble (e.g. “Here is the JSON…”) and markdown ``json`` code fences before parsing; wider parse-error log (`raw_head`). Flash scoring omits thinking by default (`GEMINI_DISABLE_THINKING_FOR_FLASH`) to preserve JSON output budget.
- **Scorer**: Default Flash output tokens 512 / retry 1024; compact retry prompt; on parse failure attach full raw text (`GeminiJsonParseError`) and regex-recover `relevance`/`novelty`/`depth`/`score` when truncated (`SCORE_FLASH_OUTPUT_TOKENS`, `SCORE_FLASH_RETRY_OUTPUT_TOKENS`).
- **Reviewer**: Higher default `REVIEWER_MAX_OUTPUT_TOKENS` (1024); regex recovery of `fact_error` / `inferred` / `needs_retry` / `review_comment` when Gemini JSON is truncated mid-field (parse errors still logged from `gemini_client`).
- **RSS / Atom feeds**: Sanitize XML before parse — strip illegal control characters and escape bare `&` outside CDATA (common broken WordPress feeds); retry parse after sanitization.

### Changed
- **Digest content richness**: Lower default synthesis gate (`ITEM_DIGEST_THEME_MIN_SUMMARIES` → `3`) so headline / themes / narrative run more often; raise Telegram per-item body budget (`MAX_SUMMARY_CHARS` → `340`).
- **Extractor**: Configurable article slice (`EXTRACTOR_MAX_INPUT_CHARS`, default `6000`); prompt requires at least one verifiable anchor in `what_happened` or `confidence=low`; structured `extraction_metrics` logs.
- **Reviewer**: If `what_happened` is shorter than `MIN_WHAT_HAPPENED_CHARS` (default `45`), trigger one grounded extraction retry (same budget as LLM `needs_retry`); `ReviewerOutput.extract_retry_used`; `summary_metrics` logs.
- **Docs**: README / `.env.example` document new tuning knobs; consolidate duplicate boilerplate in `AGENTS.md` / `CLAUDE.md`.

### Added
- `tests/test_reviewer_thin_retry.py` for thin-fact retry behavior.
- `tests/test_reviewer_partial_json.py`, `tests/test_scorer_partial_json.py`, `tests/test_rss_feed_sanitize.py` for truncated JSON recovery and feed sanitization.
- **Digest readability & observability**: Sentence-boundary `narrative_excerpt` (env `NARRATIVE_EXCERPT_MAX_CHARS`); synthesizer prompt + `build_market_takeaway` dedupe vs headline (`difflib.SequenceMatcher`); optional Apify full-page Top-K before extraction (`EXTRACTOR_FULLTEXT_TOP_K`, `EXTRACTOR_FULLTEXT_MIN_WORDS`, `EXTRACTOR_FULLTEXT_TIMEOUT_SECONDS`); structured `pipeline_run_summary` JSON log at end of `crew.run`.
- `tests/test_narrative_excerpt.py`, `tests/test_synthesizer_takeaway.py`.

## [2026-05-02]

### Fixed
- **Smart Telegram message chunking at theme boundaries**: Messages exceeding 4096 characters are now intelligently split at newline (theme) boundaries instead of hard character limits. This prevents formatting corruption and broken escape sequences under HTML `parse_mode`. Added:
  - `_smart_chunk_text()`: Splits text at theme boundaries when possible, falls back to character splitting only for oversized single lines
  - `_validate_markdown_boundaries()`: Validates chunk boundaries (legacy name; used for HTML escape integrity)
  - `TELEGRAM_CHUNK_DELAY_MS`: Configurable inter-message delay to prevent rate limiting (default 500ms)
  - Comprehensive test suite (`tests/test_telegram_chunking.py`) with 15 tests covering chunking logic and edge cases

## [2026-04-25]

### Added
- **Pre-extraction semantic deduplication**: New `is_semantically_duplicate()` method in state store detects same-batch near-duplicates before expensive extractor calls
  - SQLite and Firestore backends support 7-day embedding window with configurable cosine similarity threshold (default 0.85)
  - Reduces redundant summaries when multiple KOL sources cover the same technical story
  - Controlled by `SEMANTIC_PREFILTER_ENABLED` flag (default disabled for conservative rollout)

### Changed
- Tightened digest quality with memory context gating and unscored article tail cap
- Normalize OpenCC Taiwan terms for consistent Traditional Chinese output

## [2026-04-20]

### Added
- **Deep insight zh-TW enforcement**: All deep insight briefs now produce 100-200 character Traditional Chinese output with structured sections (Insight / Tech Rationale / Implication)
- Chinese-focused insight upgrade with localization improvements

## [2026-04-15]

### Fixed
- Skip fallback-only digests when extracted items are insufficient

## Earlier Releases

See git log for full history of scoring refinements, Gemini agent patterns, and state backend improvements.
