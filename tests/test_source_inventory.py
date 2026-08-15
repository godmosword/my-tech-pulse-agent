import yaml

from sources.earnings_fetcher import EarningsFetcher, REGISTRY_PATH, sec_document_headers
from sources.newsapi_fetcher import newsapi_enabled
from sources.rss_fetcher import KOL_REGISTRY_PATH, RSSFetcher
from sources.social_tracker import SocialTracker, social_trending_enabled

ENABLED_NEWS = {
    "techcrunch_rss",
    "theverge_rss",
    "ars_technica_rss",
    "wired_rss",
    "theregister_rss",
    "ieee_spectrum_rss",
    "huggingface_blog_rss",
    "openai_news_rss",
    "coindesk_rss",
}

DISABLED_NEWS = {
    "bloomberg_rss",
    "reuters_tech_rss",
    "decrypt_rss",
    "theblock_rss",
    "anandtech_rss",
    "semianalysis_rss",
}

IEEE_FEED_URL = "https://spectrum.ieee.org/feeds/feed.rss"


def _registry() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _news_entries() -> list[dict]:
    return [s for s in _registry()["sources"] if s.get("type", "news") == "news"]


def test_enabled_news_sources_are_the_primary_set():
    news = _news_entries()
    enabled = {s["name"] for s in news if s.get("enabled", True)}
    names = {s["name"] for s in news}
    assert enabled == ENABLED_NEWS
    assert DISABLED_NEWS <= names


def test_ieee_spectrum_uses_live_feed_url():
    by_name = {s["name"]: s for s in _news_entries()}
    assert by_name["ieee_spectrum_rss"]["url"] == IEEE_FEED_URL


def test_primary_fallback_chain():
    by_name = {s["name"]: s for s in _news_entries()}
    assert by_name["techcrunch_rss"]["fallback"] == "theverge_rss"
    assert by_name["theverge_rss"]["fallback"] == "ars_technica_rss"
    assert by_name["ars_technica_rss"]["fallback"] == "wired_rss"
    assert by_name["wired_rss"]["fallback"] == "theregister_rss"
    assert by_name["theregister_rss"]["fallback"] is None


def test_earnings_fetcher_skips_disabled_efts():
    fetcher = EarningsFetcher()
    names = [s["name"] for s in fetcher._sources]
    assert names == ["sec_edgar_earnings_rss"]
    by_name = {s["name"]: s for s in _registry()["sources"] if s.get("type") == "earnings"}
    assert by_name["sec_edgar_rss"]["enabled"] is False


def test_dead_kol_feeds_stay_in_registry_but_disabled():
    fetcher = RSSFetcher()
    assert fetcher._kol_registry["sequoia_blog"].enabled is False
    assert fetcher._kol_registry["blocktempo_opinion"].enabled is False
    with open(KOL_REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    chinese = [src for group in data["chinese_sources"].values() for src in group]
    blocktempo = next(s for s in chinese if s["name"] == "blocktempo_opinion")
    assert blocktempo["enabled"] is False


def test_newsapi_and_trending_default_off(monkeypatch):
    monkeypatch.delenv("NEWSAPI_ENABLED", raising=False)
    monkeypatch.delenv("SOCIAL_TRENDING_ENABLED", raising=False)
    assert newsapi_enabled() is False
    assert social_trending_enabled() is False


def test_social_trending_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("SOCIAL_TRENDING_ENABLED", "0")
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    assert SocialTracker().fetch_trending() == []


def test_sec_document_headers_use_env_user_agent(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "tech-pulse/0.2 inventory@example.com")
    headers = sec_document_headers()
    assert headers["User-Agent"] == "tech-pulse/0.2 inventory@example.com"
    assert "Accept-Encoding" in headers
