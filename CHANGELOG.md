# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
- **Smart Telegram message chunking at theme boundaries**: Messages exceeding 4096 characters are now intelligently split at newline (theme) boundaries instead of hard character limits. This prevents formatting corruption and broken MarkdownV2 escape sequences. Added:
  - `_smart_chunk_text()`: Splits text at theme boundaries when possible, falls back to character splitting only for oversized single lines
  - `_validate_markdown_boundaries()`: Validates that each chunk has balanced backslash escape sequences
  - `TELEGRAM_CHUNK_DELAY_MS`: Configurable inter-message delay to prevent rate limiting (default 500ms)
  - Comprehensive test suite (`tests/test_telegram_chunking.py`) with 15 tests covering chunking logic, markdown validation, and edge cases

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
