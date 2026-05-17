"""Tests for the dashboard revalidate webhook caller.

We never hit the network: every test patches urllib.request.urlopen so the
helper is exercised purely against in-memory request objects.
"""

from __future__ import annotations

import io
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from delivery.revalidate import DEFAULT_PATHS, revalidate_dashboard


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for key in (
        "DASHBOARD_REVALIDATE_URL",
        "DASHBOARD_REVALIDATE_TOKEN",
        "DASHBOARD_REVALIDATE_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_skips_when_url_or_token_missing():
    """Without both env vars set, the helper should no-op and return False."""
    assert revalidate_dashboard() is False


def test_posts_default_paths_when_configured(monkeypatch):
    monkeypatch.setenv("DASHBOARD_REVALIDATE_URL", "https://example.com/api/revalidate")
    monkeypatch.setenv("DASHBOARD_REVALIDATE_TOKEN", "secret")

    captured: list[str] = []

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def _fake_urlopen(request, timeout):  # noqa: ARG001
        captured.append(request.full_url)
        assert request.get_method() == "POST"
        assert request.headers.get("X-revalidate-token") == "secret"
        return _Resp()

    with patch("delivery.revalidate.urllib.request.urlopen", side_effect=_fake_urlopen):
        assert revalidate_dashboard() is True

    # One POST per default path, with the path query param URL-encoded.
    assert len(captured) == len(DEFAULT_PATHS)
    for url, path in zip(captured, DEFAULT_PATHS):
        assert url.startswith("https://example.com/api/revalidate?")
        assert f"path={path.replace('/', '%2F')}" in url


def test_returns_false_on_non_2xx(monkeypatch):
    monkeypatch.setenv("DASHBOARD_REVALIDATE_URL", "https://example.com/api/revalidate")
    monkeypatch.setenv("DASHBOARD_REVALIDATE_TOKEN", "secret")

    resp = MagicMock()
    resp.status = 401
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False

    with patch("delivery.revalidate.urllib.request.urlopen", return_value=resp):
        assert revalidate_dashboard(["/"]) is False


def test_swallows_http_error(monkeypatch):
    """HTTPError must never bubble up — the pipeline summary must keep printing."""
    monkeypatch.setenv("DASHBOARD_REVALIDATE_URL", "https://example.com/api/revalidate")
    monkeypatch.setenv("DASHBOARD_REVALIDATE_TOKEN", "secret")

    err = urllib.error.HTTPError(
        url="https://example.com/api/revalidate",
        code=503,
        msg="boom",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b"upstream down"),
    )
    with patch("delivery.revalidate.urllib.request.urlopen", side_effect=err):
        assert revalidate_dashboard(["/"]) is False


def test_swallows_url_error(monkeypatch):
    monkeypatch.setenv("DASHBOARD_REVALIDATE_URL", "https://example.com/api/revalidate")
    monkeypatch.setenv("DASHBOARD_REVALIDATE_TOKEN", "secret")

    with patch(
        "delivery.revalidate.urllib.request.urlopen",
        side_effect=urllib.error.URLError("dns failure"),
    ):
        assert revalidate_dashboard(["/"]) is False
