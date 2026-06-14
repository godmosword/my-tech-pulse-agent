#!/usr/bin/env bash
#
# Deploy the Firestore composite + vector indexes defined in firestore.indexes.json.
#
# This is a maintainer-run operation (not wired into CI) — it needs Firebase/GCP
# credentials. Run from the repo root.
#
# Assumptions (see docs/DEPLOY_CHECKLIST.md):
#   - FIRESTORE_COLLECTION_PREFIX=tech_pulse (the artifact hardcodes tech_pulse_* groups)
#   - Default Firestore database "(default)" (firebase.json targets the default DB)
#
# Prereqs: authenticated `firebase login` (or GOOGLE_APPLICATION_CREDENTIALS) and
# GCP_PROJECT_ID exported.
#
# Usage:
#   GCP_PROJECT_ID=my-project bash scripts/deploy_firestore_indexes.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INDEXES="$ROOT/firestore.indexes.json"

if [[ -z "${GCP_PROJECT_ID:-}" ]]; then
  echo "error: GCP_PROJECT_ID is not set" >&2
  exit 1
fi

if [[ ! -f "$INDEXES" ]]; then
  echo "error: $INDEXES not found" >&2
  exit 1
fi

# Validate the index artifact before attempting a deploy.
if ! python3 -m json.tool "$INDEXES" >/dev/null; then
  echo "error: $INDEXES is not valid JSON" >&2
  exit 1
fi

echo "Deploying Firestore indexes to project '$GCP_PROJECT_ID' (default database)..."
# Pin the CLI major for reproducibility; --non-interactive avoids hanging in CI-like envs.
npx --yes firebase-tools@13 deploy \
  --only firestore:indexes \
  --project "$GCP_PROJECT_ID" \
  --non-interactive

echo "Done. Verify with: gcloud firestore indexes composite list --project '$GCP_PROJECT_ID'"
