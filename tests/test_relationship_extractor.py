"""Tests for 10-K relationship extraction."""

from unittest.mock import patch

from agents.relationship_extractor import extract_relationships, resolve_counterparty_ticker
from agents.relationship_models import CompanyRelationships


_SOURCE = (
    "Item 1A. Risk Factors. We depend on Taiwan Semiconductor Manufacturing Company "
    "for advanced node production. Our largest customers include Microsoft Corporation "
    "and Meta Platforms. Competition includes Advanced Micro Devices and Intel Corporation. "
    + "Additional disclosure text. " * 30
)


def test_verify_quote_filters_unverified_edges():
    good_quote = "depend on Taiwan Semiconductor Manufacturing"
    bad_quote = "this sentence was never in the filing at all"

    mock_data = {
        "edges": [
            {
                "counterparty_name": "TSMC",
                "relation": "supplier",
                "quote": good_quote,
                "concentration_note": "",
            },
            {
                "counterparty_name": "Fake Corp",
                "relation": "customer",
                "quote": bad_quote,
                "concentration_note": "",
            },
        ]
    }

    with patch("agents.relationship_extractor.generate_json", return_value=(mock_data, "{}")):
        with patch("agents.relationship_extractor._gemini_client"):
            out = extract_relationships("NVDA", tenk_text=_SOURCE)

    assert len(out.edges) == 1
    assert out.edges[0].counterparty_name == "TSMC"
    assert out.edges[0].verified is True


def test_resolve_tsmc_to_tsm():
    aliases = {"tsmc": "TSM", "taiwan semiconductor": "TSM"}
    assert resolve_counterparty_ticker("TSMC", aliases) == "TSM"
    assert resolve_counterparty_ticker("Unknown Widgets Inc.", aliases) is None


def test_resolve_unknown_name_keeps_edge():
    mock_data = {
        "edges": [
            {
                "counterparty_name": "Unknown Widgets Inc.",
                "relation": "customer",
                "quote": "largest customers include Microsoft Corporation",
                "concentration_note": "",
            },
        ]
    }
    with patch("agents.relationship_extractor.generate_json", return_value=(mock_data, "{}")):
        with patch("agents.relationship_extractor._gemini_client"):
            with patch(
                "agents.relationship_extractor.resolve_counterparty_ticker",
                return_value=None,
            ):
                out = extract_relationships("NVDA", tenk_text=_SOURCE)

    assert len(out.edges) == 1
    assert out.edges[0].counterparty_ticker is None


def test_gemini_failure_returns_empty_without_raise():
    with patch(
        "agents.relationship_extractor.generate_json",
        side_effect=RuntimeError("api down"),
    ):
        with patch("agents.relationship_extractor._gemini_client"):
            out = extract_relationships("NVDA", tenk_text=_SOURCE)

    assert isinstance(out, CompanyRelationships)
    assert out.edges == []
    assert out.ticker == "NVDA"
