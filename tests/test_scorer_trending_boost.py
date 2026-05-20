"""Social trending hashtag boost on lexicon_score."""

from sources.rss_fetcher import Article
from sources.social_tracker import TrendingTopic
from scoring.scorer import Scorer


def test_trending_hashtag_boosts_lexicon_score():
    scorer = Scorer()
    scorer.set_trending_hashtags([
        TrendingTopic(platform="x", hashtag="gemini", rank=1),
    ])
    article = Article(
        title="Google introduces Gemini Spark at IO 2026",
        url="https://example.com/gemini",
        source="Example",
        summary="Gemini Spark integrates with Gmail.",
    )
    scorer._annotate_lexicon_match(article)
    assert article.lexicon_score >= 4.0
    assert any(s.startswith("trending:") for s in article.matched_signals)


def test_empty_trending_hashtags_no_boost():
    scorer = Scorer()
    scorer.set_trending_hashtags([])
    article = Article(
        title="Unrelated local news",
        url="https://example.com/local",
        source="Example",
        summary="City council meeting.",
    )
    before = scorer.match_lexicon(article.title, article.summary).lexicon_score
    scorer._annotate_lexicon_match(article)
    assert article.lexicon_score == before
