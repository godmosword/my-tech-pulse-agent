#!/usr/bin/env bash
# Post-deploy verification: API, revalidate, backfill (dry-run + optional apply).
# Usage (repo root):
#   set -a && source .env && set +a && ./scripts/local_post_deploy_verify.sh
#   ./scripts/local_post_deploy_verify.sh --apply-backfill --backfill-limit 50
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SITE_URL="${NEXT_PUBLIC_SITE_URL:-https://my-tech-pulse-agent.vercel.app}"
SITE_URL="${SITE_URL%/}"
APPLY_BACKFILL=0
BACKFILL_LIMIT=12
BACKFILL_MAX_UPDATES=8

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply-backfill) APPLY_BACKFILL=1; shift ;;
    --backfill-limit) BACKFILL_LIMIT="${2:?}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

red() { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
section() { echo ""; echo "=== $* ==="; }

section "1. API /api/v1/health"
if [[ -z "${API_READ_TOKEN:-}" ]]; then
  red "SKIP: API_READ_TOKEN not set"
else
  code=$(curl -sS -o /tmp/tp_health.json -w "%{http_code}" \
    -H "Authorization: Bearer ${API_READ_TOKEN}" \
    "${SITE_URL}/api/v1/health")
  echo "HTTP ${code}"
  cat /tmp/tp_health.json
  echo ""
  [[ "$code" == "200" ]] && green "health OK" || red "health failed"
fi

section "2. API digest/today (snippet)"
if [[ -n "${API_READ_TOKEN:-}" ]]; then
  curl -sS -H "Authorization: Bearer ${API_READ_TOKEN}" \
    "${SITE_URL}/api/v1/digest/today" | head -c 800
  echo ""
fi

section "3. ISR revalidate"
if [[ -z "${REVALIDATE_TOKEN:-}" ]]; then
  red "SKIP: REVALIDATE_TOKEN not set"
else
  code=$(curl -sS -o /tmp/tp_reval.json -w "%{http_code}" -X POST \
    "${SITE_URL}/api/revalidate?path=/" \
    -H "x-revalidate-token: ${REVALIDATE_TOKEN}")
  echo "HTTP ${code}"
  cat /tmp/tp_reval.json
  echo ""
  [[ "$code" == "200" ]] && green "revalidate OK" || red "revalidate failed (check token matches Vercel)"
fi

section "4. Backfill zh fields (dry-run)"
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  red "SKIP: GEMINI_API_KEY not set (needed for backfill)"
else
  python3 scripts/backfill_zh_fields.py --dry-run --limit "${BACKFILL_LIMIT}" --max-updates "${BACKFILL_MAX_UPDATES}"
  if [[ "$APPLY_BACKFILL" == "1" ]]; then
    section "4b. Backfill apply"
    python3 scripts/backfill_zh_fields.py --limit "${BACKFILL_LIMIT}" --max-updates "${BACKFILL_MAX_UPDATES}"
    if [[ -n "${REVALIDATE_TOKEN:-}" ]]; then
      curl -sS -X POST "${SITE_URL}/api/revalidate?path=/" \
        -H "x-revalidate-token: ${REVALIDATE_TOKEN}" >/dev/null
      green "revalidate after backfill sent"
    fi
  else
    echo "(dry-run only; re-run with --apply-backfill to write)"
  fi
fi

section "5. pytest (excludes optional LLM-as-judge; needs real genai + billing)"
python3 -m pytest -q --ignore=tests/judge_test.py

section "Done"
