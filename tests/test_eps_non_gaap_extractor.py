from agents.eps_non_gaap_extractor import extract_non_gaap_eps_diluted


def test_extract_non_gaap_eps():
    text = "We reported non-GAAP diluted EPS of $5.25 for the quarter ended April 2026."
    assert extract_non_gaap_eps_diluted(text) == 5.25


def test_extract_returns_none_without_match():
    assert extract_non_gaap_eps_diluted("GAAP EPS was $2.00") is None
