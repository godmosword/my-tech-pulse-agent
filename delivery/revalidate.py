"""Webhook caller that flushes the dashboard's ISR cache after a pipeline run.

Stdlib-only (urllib) so the pipeline keeps zero extra deps. The dashboard
exposes POST /api/revalidate gated by a shared token; we no-op silently when
either DASHBOARD_REVALIDATE_URL or DASHBOARD_REVALIDATE_TOKEN is unset, which
is the common case for local dev and CI smoke runs.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

logger = logging.getLogger(__name__)

DEFAULT_PATHS: tuple[str, ...] = ("/", "/archive")
REVALIDATE_TIMEOUT_SECONDS = float(os.getenv("DASHBOARD_REVALIDATE_TIMEOUT", "5"))


def revalidate_dashboard(paths: Iterable[str] = DEFAULT_PATHS) -> bool:
    """POST to the dashboard's revalidate webhook for each path.

    Returns True when every configured POST returned 2xx, False if any failed
    or the webhook is not configured. Failures are logged at WARNING but never
    raise — the dashboard refresh is best-effort and must not block the
    pipeline run summary.
    """
    base_url = (os.getenv("DASHBOARD_REVALIDATE_URL") or "").strip().rstrip("/")
    token = (os.getenv("DASHBOARD_REVALIDATE_TOKEN") or "").strip()
    if not base_url or not token:
        logger.debug("Dashboard revalidate skipped: URL or token not configured")
        return False

    all_ok = True
    for path in paths:
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{base_url}?{urllib.parse.urlencode({'path': normalized})}"
        request = urllib.request.Request(
            url,
            method="POST",
            headers={
                "x-revalidate-token": token,
                "content-type": "application/json",
            },
            data=b"",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 — fixed scheme, env-controlled host
                request, timeout=REVALIDATE_TIMEOUT_SECONDS
            ) as response:
                status = response.status
                if 200 <= status < 300:
                    logger.info("Dashboard revalidated %s (%d)", normalized, status)
                else:
                    all_ok = False
                    logger.warning(
                        "Dashboard revalidate %s returned %d", normalized, status
                    )
        except urllib.error.HTTPError as exc:
            all_ok = False
            logger.warning(
                "Dashboard revalidate %s HTTPError %d: %s",
                normalized,
                exc.code,
                _safe_read(exc),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            all_ok = False
            logger.warning("Dashboard revalidate %s failed: %s", normalized, exc)
    return all_ok


def _safe_read(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
        return body[:200]
    except Exception:  # noqa: BLE001 — best effort
        return ""


__all__ = ["revalidate_dashboard", "DEFAULT_PATHS"]
