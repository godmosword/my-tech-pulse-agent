# Earnings vendor API evaluation (S4)

Status: **stub only** — `EARNINGS_VENDOR_MODE=off` by default. SEC XBRL remains the sole required path.

## Candidates

| Provider | Free tier | Estimates / calendar | Transcripts | Notes |
|----------|-----------|----------------------|-------------|-------|
| SEC EDGAR XBRL | Yes | No consensus | No | Primary source of truth |
| FMP | Basic ~250 calls/day | Calendar, estimates (plan-dependent) | Limited | Wire via `FMP_API_KEY` |
| Finnhub | Dashboard quota | Calendar, estimates | Some | Wire via `FINNHUB_API_KEY` |

## Integration rules (implemented)

1. `sources/vendor_earnings_provider.py` — `VendorEarningsProvider` with `enrich_ticker()` stub.
2. Vendor failure never adds `critical_errors`; pipeline continues SEC-only.
3. `MAX_VENDOR_CALLS_PER_RUN` caps per Cloud Run execution.
4. Estimates must include `source_type: vendor_estimate` or fact_guard drops them.

## Next steps (when enabling)

1. Implement `sources/fmp_provider.py` and `sources/finnhub_provider.py` behind the abstraction.
2. Record calls in `tech_pulse_vendor_api_usage` (Firestore) with TTL caches.
3. Re-run free-tier endpoint probes and update the table above with 403/restricted flags.

## Env

See `.env.example`: `EARNINGS_VENDOR_MODE`, `FMP_API_KEY`, `FINNHUB_API_KEY`, `MAX_VENDOR_CALLS_PER_RUN`.
