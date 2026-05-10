"""Allowed-themes whitelist for soft KOL sources (Lenny, Manny, BlockTrend, BlockTempo)."""

from sources.rss_fetcher import RSSFetcher


def test_lennys_newsletter_allowed_themes_loaded():
    fetcher = RSSFetcher()
    cfg = fetcher._kol_registry["lenny_newsletter"]
    assert cfg.allowed_themes == ["產品與策略", "其他焦點"]


def test_manny_newsletter_allowed_themes_includes_ai_infrastructure():
    fetcher = RSSFetcher()
    cfg = fetcher._kol_registry["manny_newsletter"]
    assert "AI 基礎設施" in cfg.allowed_themes
    assert "產品與策略" in cfg.allowed_themes


def test_chinese_crypto_kols_restricted_to_research_themes():
    fetcher = RSSFetcher()
    for name in ("blocktrend", "blocktempo_opinion"):
        cfg = fetcher._kol_registry[name]
        assert cfg.allowed_themes == ["技術研發", "其他焦點"], name


def test_unrestricted_kols_have_empty_allowed_themes():
    """Technical KOLs (semianalysis, simon_willison, etc.) are NOT theme-restricted."""
    fetcher = RSSFetcher()
    for name in ("semianalysis", "simon_willison", "latent_space", "interconnects_ai"):
        cfg = fetcher._kol_registry[name]
        assert cfg.allowed_themes == [], name
