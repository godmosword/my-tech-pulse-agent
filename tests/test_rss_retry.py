"""Retry behavior for RSSFetcher._get_with_retry on transient failures."""

import httpx
import pytest

from sources import rss_fetcher
from sources.rss_fetcher import RSSFetcher

VALID_RSS = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    "<item><title>Hello</title>"
    "<link>http://example.com/a</link><description>d</description></item>"
    "</channel></rss>"
)


def _response(status: int, *, text: str = "", headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        text=text,
        headers=headers or {},
        request=httpx.Request("GET", "http://example.com/feed"),
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(rss_fetcher.time, "sleep", lambda _: None)


def _make_fetcher() -> RSSFetcher:
    return RSSFetcher.__new__(RSSFetcher)


def _patch_get(monkeypatch, responses):
    """Patch httpx.Client.get to yield queued responses/exceptions in order."""
    calls = {"n": 0}
    queue = list(responses)

    def fake_get(self, url, headers=None):  # noqa: ANN001
        calls["n"] += 1
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    return calls


def test_retries_on_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 2)
    calls = _patch_get(
        monkeypatch,
        [httpx.TimeoutException("boom"), _response(200, text=VALID_RSS)],
    )
    fetcher = _make_fetcher()
    resp = fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_retries_on_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 2)
    calls = _patch_get(
        monkeypatch,
        [_response(503), _response(200, text=VALID_RSS)],
    )
    fetcher = _make_fetcher()
    resp = fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_no_retry_on_404(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 3)
    calls = _patch_get(monkeypatch, [_response(404)])
    fetcher = _make_fetcher()
    resp = fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert resp.status_code == 404
    assert calls["n"] == 1


def test_no_retry_on_304(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 3)
    calls = _patch_get(monkeypatch, [_response(304)])
    fetcher = _make_fetcher()
    resp = fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert resp.status_code == 304
    assert calls["n"] == 1


def test_exhausts_retries_and_raises(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 2)
    calls = _patch_get(
        monkeypatch,
        [httpx.ConnectError("down"), httpx.ConnectError("down")],
    )
    fetcher = _make_fetcher()
    with pytest.raises(httpx.TransportError):
        fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert calls["n"] == 2


def test_attempts_one_disables_retry(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 1)
    calls = _patch_get(monkeypatch, [httpx.TimeoutException("boom")])
    fetcher = _make_fetcher()
    with pytest.raises(httpx.TimeoutException):
        fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert calls["n"] == 1


def test_honors_retry_after_header(monkeypatch):
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 2)
    captured: list[float] = []
    monkeypatch.setattr(rss_fetcher.time, "sleep", lambda s: captured.append(s))
    _patch_get(
        monkeypatch,
        [_response(429, headers={"Retry-After": "3"}), _response(200, text=VALID_RSS)],
    )
    fetcher = _make_fetcher()
    resp = fetcher._get_with_retry("http://example.com/feed", {})  # noqa: SLF001
    assert resp.status_code == 200
    assert captured == [3.0]


def test_retry_after_capped(monkeypatch):
    resp = _response(429, headers={"Retry-After": "999"})
    assert rss_fetcher._retry_after_sec(resp) == rss_fetcher._RETRY_AFTER_CAP_SEC


def test_kol_source_recovers_after_timeout(monkeypatch):
    """End-to-end through _fetch_kol_source: transient timeout then parsed KOL article."""
    monkeypatch.setattr(rss_fetcher, "RSS_MAX_ATTEMPTS", 2)
    _patch_get(
        monkeypatch,
        [httpx.TimeoutException("boom"), _response(200, text=VALID_RSS)],
    )
    fetcher = _make_fetcher()
    fetcher._etag_cache = {}
    fetcher._last_modified_cache = {}
    kol = rss_fetcher.KOLConfig(
        name="test_kol",
        author="Test Author",
        url="http://example.com/feed",
        tier="deep",
        domain=["ai"],
    )
    articles = fetcher._fetch_kol_source(kol)  # noqa: SLF001
    assert len(articles) == 1
    assert articles[0].author == "Test Author"
    assert articles[0].label == "kol"
    assert articles[0].tier == "deep"
