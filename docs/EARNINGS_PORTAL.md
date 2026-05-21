# Earnings Portal — `tech_pulse_earnings_reports`

Collection: `{FIRESTORE_COLLECTION_PREFIX}_earnings_reports` (default `tech_pulse_earnings_reports`).

Document id: `{ticker}_{fiscal_year}_{fiscal_period}` (see `build_report_id`).

## Schema `earnings_v2`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `report_id` | string | yes | Same as doc id |
| `ticker` | string | yes | Uppercase |
| `company` | string | yes | |
| `cik` | string | yes | |
| `tier` | int \| null | no | Watchlist tier 1–5 |
| `fiscal_year` | int \| null | no | Company fiscal year |
| `fiscal_period` | string | yes | e.g. `FY2026Q1` |
| `period_end` | timestamp | no | |
| `quarter_label` | string | yes | zh display label |
| `published_at` | timestamp | yes | SEC filed time (UTC) — **sort key** |
| `filed_at` | timestamp | no | |
| `headline_metrics` | EarningsFact[] | yes | SEC XBRL only in v2 pipeline |
| `segment_metrics` | EarningsFact[] | no | |
| `guidance` | object | no | `wording` from narrative extractor |
| `estimates` | object | no | Vendor only when `EARNINGS_VENDOR_MODE` enabled |
| `surprise` | object | no | Vendor |
| `key_quotes` | string[] | no | Substring-verified against filing |
| `management_tone` | string | no | |
| `ai_infra_relevance` | string | no | English narrative snippet |
| `ai_infra_signal` | enum | no | `strong` \| `medium` \| `weak` \| `not_relevant` |
| `investment_takeaway_zh` | string | no | Analyzer output |
| `risk_flags` | string[] | no | zh-TW bullets |
| `earnings_quality_score` | float | no | 0–10 |
| `market_surprise_level` | enum | no | `high` \| `medium` \| `low` \| `unknown` |
| `source_documents` | SourceDocument[] | yes | `filing_url`, `form_type`, `accession` |
| `confidence` | enum | yes | `high` \| `medium` \| `low` |
| `schema_version` | string | yes | `earnings_v2` |

### EarningsFact

| Field | Notes |
|-------|-------|
| `source_type` | `sec_xbrl` or `vendor_*` |
| `source_tag` | XBRL concept tag (required for SEC facts) |
| `value` | Numeric — never LLM-derived in headline_metrics |

## REST (Dashboard)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/earnings?limit=&ticker=&max_tier=` | Recent reports |
| `GET /api/v1/earnings/report/{reportId}` | Single report |
| `GET /api/v1/earnings/calendar?horizon=30` | Calendar stub (recent filings + future vendor) |

Bearer: `API_READ_TOKEN`.

## Pipeline metrics (`pipeline_run_summary`)

- `earnings_filings_seen`
- `earnings_xbrl_facts_loaded`
- `earnings_vendor_calls`
- `earnings_reports_archived`
- `earnings_sec_only_count`
- `earnings_vendor_enriched_count`
- `earnings_telegram_candidates`

## Compatibility

`tech_pulse_memory_items` with `kind=earnings` remains for Portal v1. Dashboard earnings pages read `tech_pulse_earnings_reports` first.
