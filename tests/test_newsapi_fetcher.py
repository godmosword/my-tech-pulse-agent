from sources.newsapi_fetcher import NewsApiFetcher


def test_newsapi_skips_without_key(monkeypatch):
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    fetcher = NewsApiFetcher(api_key="")
    assert fetcher.fetch() == []


def test_newsapi_parses_article(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "ok",
                "articles": [
                    {
                        "title": "Gemini update",
                        "url": "https://example.com/gemini",
                        "description": "Google announced Gemini.",
                        "content": "Full text.",
                        "publishedAt": "2026-05-20T08:00:00Z",
                        "source": {"name": "Example News"},
                    }
                ],
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr("sources.newsapi_fetcher.httpx.Client", FakeClient)
    articles = NewsApiFetcher(api_key="test-key").fetch(limit=5)
    assert len(articles) == 1
    assert articles[0].title == "Gemini update"
    assert articles[0].url == "https://example.com/gemini"
    assert articles[0].source == "Example News"
