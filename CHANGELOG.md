# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [2026-05-06]

### Changed
- **Digest content richness**: Lower default synthesis gate (`ITEM_DIGEST_THEME_MIN_SUMMARIES` → `3`) so headline / themes / narrative run more often; raise Telegram per-item body budget (`MAX_SUMMARY_CHARS` → `340`).
- **Extractor**: Configurable article slice (`EXTRACTOR_MAX_INPUT_CHARS`, default `6000`); prompt requires at least one verifiable anchor in `what_happened` or `confidence=low`; structured `extraction_metrics` logs.
- **Reviewer**: If `what_happened` is shorter than `MIN_WHAT_HAPPENED_CHARS` (default `45`), trigger one grounded extraction retry (same budget as LLM `needs_retry`); `ReviewerOutput.extract_retry_used`; `summary_metrics` logs.
- **Docs**: README / `.env.example` document new tuning knobs; consolidate duplicate boilerplate in `AGENTS.md` / `CLAUDE.md`.

### Added
- `tests/test_reviewer_thin_retry.py` for thin-fact retry behavior.
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
