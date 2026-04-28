"""LLM-as-judge output quality gate.

These tests use Gemini itself to evaluate the quality of pipeline outputs.
They require GEMINI_API_KEY and are intended to run in CI after the smoke tests pass.
Skip automatically if the API key is not set.
"""

import json
import os
import textwrap
import time

import pytest
from google import genai
from google.genai import types

pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping LLM-as-judge tests",
)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
JUDGE_SYSTEM = textwrap.dedent("""\
    You are a strict quality evaluator for AI-generated tech news summaries.
    Evaluate the given output and respond with a JSON object:
    {
      "pass": true | false,
      "score": 0-10,
      "issues": ["list of specific problems, empty if none"]
    }
    Be objective. A score of 7+ passes. Output JSON only.
""")


def _judge(prompt: str, retries: int = 3) -> dict:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=JUDGE_SYSTEM,
                    max_output_tokens=512,
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return {}  # unreachable


def test_judge_article_summary_no_hallucination():
    """Judge verifies extractor summary doesn't add facts not in source."""
    source_text = "Apple reported $98.9 billion in quarterly revenue, beating analyst estimates."
    summary = "Apple reported quarterly revenue of $98.9 billion, which exceeded analyst expectations."

    prompt = textwrap.dedent(f"""\
        Source text:
        {source_text}

        Generated summary:
        {summary}

        Check: Does the summary add any facts NOT present in the source text?
        Evaluate for hallucination (adding unsupported claims) and factual accuracy.
    """)

    result = _judge(prompt)
    assert result["pass"] is True, f"Judge failed: {result.get('issues')}"
    assert result["score"] >= 7


def test_judge_article_summary_hallucination_detected():
    """Judge should catch hallucinated facts."""
    source_text = "Apple reported $98.9 billion in quarterly revenue."
    hallucinated_summary = (
        "Apple reported $98.9 billion in quarterly revenue, a 12% year-over-year increase, "
        "beating analyst estimates of $97.1 billion."
    )

    prompt = textwrap.dedent(f"""\
        Source text:
        {source_text}

        Generated summary:
        {hallucinated_summary}

        Check: Does the summary add any facts NOT present in the source text?
        The summary claims YoY growth rate and analyst estimates — verify if those are in the source.
    """)

    result = _judge(prompt)
    assert len(result.get("issues", [])) > 0, "Judge should have detected hallucinated facts"


def test_judge_earnings_fact_guard():
    """Judge verifies earnings output only contains numbers from the source."""
    source_text = "Revenue was $124.3 billion. EPS was $2.40 per diluted share."
    earnings_json = json.dumps({
        "company": "Apple",
        "quarter": "Q1 FY2026",
        "revenue": {"actual": 124.3, "estimate": None, "beat_pct": None},
        "eps": {"actual": 2.40, "estimate": None},
        "segments": {},
        "guidance_next_q": None,
        "key_quotes": ["Revenue was $124.3 billion."],
        "source": "SEC 10-Q",
        "confidence": "high",
    })

    prompt = textwrap.dedent(f"""\
        Source text:
        {source_text}

        Extracted earnings JSON:
        {earnings_json}

        Check: Are ALL numeric values in the JSON explicitly present in the source text?
        Does the extraction follow fact_guard rules (no inferred or calculated numbers)?
    """)

    result = _judge(prompt)
    assert result["pass"] is True, f"fact_guard check failed: {result.get('issues')}"


def test_judge_digest_narrative_quality():
    """Judge evaluates digest narrative for clarity and factual grounding."""
    summaries_context = json.dumps([
        {"entity": "OpenAI", "summary": "OpenAI launched GPT-5.", "confidence": "high"},
        {"entity": "Google", "summary": "Google announced Gemini 2.0.", "confidence": "high"},
    ])
    narrative = (
        "This week's tech landscape was dominated by AI model releases. "
        "OpenAI launched GPT-5 while Google unveiled Gemini 2.0, "
        "signalling continued investment in foundation models from major players."
    )

    prompt = textwrap.dedent(f"""\
        Input summaries:
        {summaries_context}

        Generated narrative:
        {narrative}

        Evaluate: Is the narrative grounded in the summaries? Is it clear, professional,
        and free of unsupported claims? Score the writing quality and factual accuracy.
    """)

    result = _judge(prompt)
    assert result["pass"] is True, f"Narrative quality check failed: {result.get('issues')}"
    assert result["score"] >= 7
