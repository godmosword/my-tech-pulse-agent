#!/usr/bin/env bash
# Provision a read-only Firestore service account for the dashboard.
#
# Creates:
#   - SA  tech-pulse-dashboard@$PROJECT.iam.gserviceaccount.com
#   - IAM  roles/datastore.viewer on $PROJECT
#   - Key file  dashboard-sa.json  (saved next to this script, gitignored)
#
# Why a dedicated SA: dashboard only reads tech_pulse_memory_items. Pipeline
# writes use a separate, write-capable identity — keep blast radius small.
#
# Usage:
#   PROJECT_ID=my-tech-pulse-agent-494715 ./scripts/setup_dashboard_sa.sh
#
# Then load the key into Vercel:
#   base64 -i dashboard-sa.json -o dashboard-sa.json.b64
#   # paste dashboard-sa.json.b64 contents into the Vercel env var
#   #   FIREBASE_SERVICE_ACCOUNT_JSON
#
# The script is idempotent: re-running only creates resources that are missing.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: set PROJECT_ID or run 'gcloud config set project <id>' first" >&2
  exit 1
fi

SA_NAME="${SA_NAME:-tech-pulse-dashboard}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_PATH="${KEY_PATH:-$(dirname "$0")/../dashboard-sa.json}"

echo "Project        : $PROJECT_ID"
echo "Service account: $SA_EMAIL"
echo "Key path       : $KEY_PATH"
echo

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "[1/3] Creating service account $SA_NAME ..."
  gcloud iam service-accounts create "$SA_NAME" \
    --project "$PROJECT_ID" \
    --display-name "Tech Pulse Dashboard (read-only)" \
    --description "Read-only access to Firestore tech_pulse_memory_items for the dashboard web reader."
else
  echo "[1/3] Service account already exists, skipping create."
fi

echo "[2/3] Binding roles/datastore.viewer on $PROJECT_ID ..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SA_EMAIL" \
  --role "roles/datastore.viewer" \
  --condition=None \
  --quiet >/dev/null

if [[ -f "$KEY_PATH" ]]; then
  echo "[3/3] Key file already exists at $KEY_PATH — not overwriting."
  echo "      Delete it and re-run to rotate."
else
  echo "[3/3] Creating key at $KEY_PATH ..."
  gcloud iam service-accounts keys create "$KEY_PATH" \
    --iam-account "$SA_EMAIL" \
    --project "$PROJECT_ID"
  chmod 600 "$KEY_PATH"
fi

echo
echo "Done. Next steps:"
echo "  1. base64 -i $KEY_PATH | pbcopy            # macOS"
echo "  2. Paste into Vercel env var FIREBASE_SERVICE_ACCOUNT_JSON"
echo "  3. Set GOOGLE_CLOUD_PROJECT=$PROJECT_ID in the same env"
echo "  4. Add $KEY_PATH to .gitignore (already covered by *.json patterns)"
