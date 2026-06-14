#!/usr/bin/env bash
#
# Create/update a Cloud Scheduler job that triggers the Cloud Run Job on a cron.
# This is the reliable production path (vs the best-effort GitHub schedule).
# Maintainer-run; needs gcloud auth with permission to manage Scheduler jobs.
#
# Required IAM (one-time, NOT covered by the GitHub WIF setup):
#   - A service account (SCHEDULER_SA) with roles/run.invoker on the Cloud Run Job
#   - Your user/SA needs roles/cloudscheduler.admin to create the scheduler job
#   - Cloud Scheduler + Cloud Run APIs enabled
#
# Auth note: the target is run.googleapis.com (a *.googleapis.com endpoint), so
# Cloud Scheduler must use an OAuth token (NOT OIDC).
#
# The :run endpoint only STARTS an execution; it does not wait for completion.
# Monitor outcomes via the pipeline failure alert (delivery/pipeline_alert.py)
# and pipeline_run_summary logs.
#
# Usage:
#   GCP_PROJECT_ID=p GCP_REGION=r CLOUD_RUN_SERVICE=job \
#   SCHEDULER_SA=sched@p.iam.gserviceaccount.com \
#   SCHEDULE="0 9 * * 1-5" [DRY_RUN=1] bash scripts/setup_cloud_scheduler.sh

set -euo pipefail

: "${GCP_PROJECT_ID:?set GCP_PROJECT_ID}"
: "${GCP_REGION:?set GCP_REGION}"
: "${CLOUD_RUN_SERVICE:?set CLOUD_RUN_SERVICE (the Cloud Run Job name)}"
: "${SCHEDULER_SA:?set SCHEDULER_SA (service account email with run.invoker)}"
SCHEDULE="${SCHEDULE:-0 9 * * 1-5}"
JOB_NAME="${SCHEDULER_JOB_NAME:-${CLOUD_RUN_SERVICE}-schedule}"
TIME_ZONE="${TIME_ZONE:-Asia/Taipei}"

RUN_URI="https://run.googleapis.com/v2/projects/${GCP_PROJECT_ID}/locations/${GCP_REGION}/jobs/${CLOUD_RUN_SERVICE}:run"

# Idempotent: update if the scheduler job exists, else create.
if gcloud scheduler jobs describe "$JOB_NAME" --location "$GCP_REGION" --project "$GCP_PROJECT_ID" >/dev/null 2>&1; then
  ACTION="update"
else
  ACTION="create"
fi

CMD=(gcloud scheduler jobs "$ACTION" http "$JOB_NAME"
  --location "$GCP_REGION"
  --project "$GCP_PROJECT_ID"
  --schedule "$SCHEDULE"
  --time-zone "$TIME_ZONE"
  --uri "$RUN_URI"
  --http-method POST
  --oauth-service-account-email "$SCHEDULER_SA")

echo "+ ${CMD[*]}"
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "DRY_RUN=1 — not executing."
  exit 0
fi
"${CMD[@]}"
echo "Scheduler job '$JOB_NAME' ${ACTION}d (schedule='$SCHEDULE' tz=$TIME_ZONE)."
