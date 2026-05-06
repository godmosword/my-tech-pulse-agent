"""Reviewer partial/truncated Gemini JSON recovery."""

from agents.reviewer_agent import ReviewResult, _recover_review_result_from_partial_json


def test_recover_truncated_mid_review_comment_like_cloud_run_log():
    # Log preview matched Cloud Run: truncated after `"inferred": true,` mid next key/string.
    raw = '{\n  "fact_error": false,\n  "inferred": true,\n  "'
    out = _recover_review_result_from_partial_json(raw)
    assert out is not None
    assert out.fact_error is False
    assert out.inferred is True
    assert out.needs_retry is False
    assert out.review_comment is None


def test_recover_with_needs_retry_and_comment():
    raw = (
        '{"fact_error": true, "inferred": false, "needs_retry": true, '
        '"review_comment": "Add concrete anchor"}'
    )
    out = _recover_review_result_from_partial_json(raw)
    assert out is not None
    assert out.fact_error is True
    assert out.needs_retry is True
    assert out.review_comment == "Add concrete anchor"


def test_recover_review_comment_null():
    raw = '{"fact_error": false, "inferred": false, "needs_retry": false, "review_comment": null}'
    out = _recover_review_result_from_partial_json(raw)
    assert out is not None
    assert out.review_comment is None


def test_recover_requires_fact_error_and_inferred():
    raw = '{"fact_error": false'
    assert _recover_review_result_from_partial_json(raw) is None


def test_review_result_defaults_match_recovered_empty_comment():
    assert ReviewResult() == ReviewResult(
        fact_error=False,
        inferred=False,
        needs_retry=False,
        review_comment=None,
    )
