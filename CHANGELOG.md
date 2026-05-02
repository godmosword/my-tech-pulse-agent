# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
