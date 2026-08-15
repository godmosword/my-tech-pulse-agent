import yaml

from sources.earnings_fetcher import sec_document_headers
from sources.newsapi_fetcher import newsapi_enabled
from sources.rss_fetcher import REGISTRY_PATH
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


def _news_entries() -> list[dict]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [s for s in data["sources"] if s.get("type", "news") == "news"]


def test_enabled_news_sources_are_the_primary_set():
    news = _news_entries()
    enabled = {s["name"] for s in news if s.get("enabled", True)}
    names = {s["name"] for s in news}
    assert enabled == ENABLED_NEWS
    assert DISABLED_NEWS <= names


def test_primary_fallback_chain():
    by_name = {s["name"]: s for s in _news_entries()}
    assert by_name["techcrunch_rss"]["fallback"] == "theverge_rss"
    assert by_name["theverge_rss"]["fallback"] == "ars_technica_rss"
    assert by_name["ars_technica_rss"]["fallback"] == "wired_rss"
    assert by_name["wired_rss"]["fallback"] == "theregister_rss"
    assert by_name["theregister_rss"]["fallback"] is None


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
