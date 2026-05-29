#!/usr/bin/env bash
# Enable Finnhub on Cloud Run Job — run only after maintainer approval.
set -euo pipefail

JOB=""
REGION="${GCP_REGION:-us-central1}"

usage() {
  echo "Usage: $0 --job CLOUD_RUN_JOB_NAME [--region REGION]"
  echo "Requires FINNHUB_API_KEY in environment, or prompts interactively."
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --job) JOB="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

[[ -n "$JOB" ]] || usage

if [[ -z "${FINNHUB_API_KEY:-}" ]]; then
  read -rsp "FINNHUB_API_KEY: " FINNHUB_API_KEY
  echo
fi

if [[ -z "$FINNHUB_API_KEY" ]]; then
  echo "FINNHUB_API_KEY is required." >&2
  exit 1
fi

echo "Updating Cloud Run job: $JOB (region=$REGION)"
echo "Setting EARNINGS_VENDOR_MODE=free, EARNINGS_REPORTS_ENABLED=1"

gcloud run jobs update "$JOB" \
  --region="$REGION" \
  --update-env-vars="EARNINGS_VENDOR_MODE=free,EARNINGS_REPORTS_ENABLED=1,FINNHUB_API_KEY=${FINNHUB_API_KEY}"

echo "Done. Trigger the job and verify earnings_vendor_enriched_count > 0 in logs."
echo "See docs/FINNHUB_PRODUCTION_SETUP.md for rollback and verification."
