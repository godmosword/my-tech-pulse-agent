"""Pillar alias contract tests (mirrors dashboard/lib/news-api.ts)."""


def normalize_pillar(value: str) -> str:
    aliases = {
        "ai": ["ai", "artificial intelligence", "llm"],
        "semiconductor": ["semiconductor", "chip", "hbm", "半導體"],
        "crypto": ["crypto", "bitcoin", "btc", "加密"],
    }
    text = (value or "").strip().lower()
    if not text:
        return ""
    for canonical, words in aliases.items():
        if text == canonical or text in words:
            return canonical
    return ""


def test_normalize_pillar():
    assert normalize_pillar("AI") == "ai"
    assert normalize_pillar("半導體") == "semiconductor"
    assert normalize_pillar("unknown") == ""
