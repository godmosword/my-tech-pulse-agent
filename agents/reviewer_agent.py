"""Stage 2.5 — Reviewer Agent: fact-grounding check and quality gate.

Sits between ExtractorAgent and SynthesizerAgent. Checks three things:
1. fact_error  — what_happened contains numbers not present verbatim in source text
2. inferred    — why_it_matters makes causal claims with no source basis → prepend [INFERRED]
3. needs_retry — why_it_matters is generic with no specific entity or mechanism

On needs_retry=True: ExtractorAgent reruns once with review_comment as feedback.
After max_retry=1: approve with confidence="low" regardless of output quality.
"""

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel

from agents.extractor_agent import ArticleSummary, ExtractorAgent
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

SYSTEM_PROMPT = (
    "You are a fact-checking editor. Your job is to verify grounding, not to rewrite. "
    "Be specific about what is missing, not generic. "
    "Output ONLY valid JSON. Do not include any text before or after the JSON object. "
    "Do not use markdown code fences."
)

REVIEW_PROMPT = """\
Review the extracted summary below against the source text.

Check three things and reply with JSON only. Do not include any text before or after the JSON object.

1. "fact_error": true if what_happened contains any specific number (e.g. "$100M", "40%", "Q3 2025")
   that does NOT appear verbatim in the source text. false otherwise.

2. "inferred": true if why_it_matters makes a causal or predictive claim that has no supporting
   sentence in the source text (e.g. "this will cause X" when source never says that). false otherwise.

3. "needs_retry": true if why_it_matters is completely generic — contains no specific company name,
   product, number, or mechanism (e.g. "this is significant for the industry" with nothing else).
   false otherwise.

4. "review_comment": if needs_retry is true, write one sentence explaining exactly what specific
   information is missing. If needs_retry is false, set to null.

Source text (excerpt):
{source_text}

Extracted summary:
- what_happened: {what_happened}
- why_it_matters: {why_it_matters}

Reply ONLY with valid JSON:
{{"fact_error": bool, "inferred": bool, "needs_retry": bool, "review_comment": "string or null"}}
"""

RETRY_SUFFIX = "\n\n[Reviewer feedback — address this in your revised output]: {comment}"


class ReviewResult(BaseModel):
    fact_error: bool = False
    inferred: bool = False
    needs_retry: bool = False
    review_comment: Optional[str] = None


class ReviewerOutput(BaseModel):
    item_id: str
    approved: bool
    needs_retry: bool
    fact_error: bool
    inferred: bool
    review_comment: Optional[str]
    final_output: Optional[ArticleSummary]


class ReviewerAgent:
    """Reviews ArticleSummary outputs for hallucination and quality before synthesis."""

    def __init__(self):
        self._client = None
        self._extractor = ExtractorAgent()

    def review(self, summary: ArticleSummary, retry_count: int = 0) -> ReviewerOutput:
        item_id = self._make_id(summary.source_url)
        source_text = summary.source_text or summary.summary

        result = self._call_reviewer(summary, source_text)

        if result.fact_error:
            logger.warning(
                "fact_error flagged for '%s' — numbers may not match source",
                summary.title[:60],
            )
            return ReviewerOutput(
                item_id=item_id,
                approved=True,  # still deliver, but confidence degrades
                needs_retry=False,
                fact_error=True,
                inferred=result.inferred,
                review_comment=result.review_comment,
                final_output=self._apply_flags(summary, result),
            )

        if result.inferred:
            summary = self._apply_inferred_prefix(summary)

        if result.needs_retry and retry_count < 1:
            logger.info(
                "needs_retry for '%s': %s — retrying extraction",
                summary.title[:60],
                result.review_comment,
            )
            retried = self._retry_extraction(summary, result.review_comment or "")
            if retried:
                retried.confidence = "low"
                return ReviewerOutput(
                    item_id=item_id,
                    approved=True,
                    needs_retry=False,
                    fact_error=False,
                    inferred=False,
                    review_comment=result.review_comment,
                    final_output=retried,
                )
            # retry produced nothing — fall through to approve with low confidence
            summary.confidence = "low"

        if result.needs_retry:
            summary.confidence = "low"

        return ReviewerOutput(
            item_id=item_id,
            approved=True,
            needs_retry=False,
            fact_error=False,
            inferred=result.inferred,
            review_comment=result.review_comment if result.needs_retry else None,
            final_output=self._apply_flags(summary, result),
        )

    def review_batch(self, summaries: list[ArticleSummary]) -> list[ReviewerOutput]:
        outputs = []
        for summary in summaries:
            try:
                output = self.review(summary)
                outputs.append(output)
            except Exception as exc:
                logger.error("Reviewer failed for '%s': %s", summary.title[:60], exc)
                # fail-open: pass through with unchanged summary
                outputs.append(ReviewerOutput(
                    item_id=self._make_id(summary.source_url),
                    approved=True,
                    needs_retry=False,
                    fact_error=False,
                    inferred=False,
                    review_comment=None,
                    final_output=summary,
                ))
        return outputs

    def _call_reviewer(self, summary: ArticleSummary, source_text: str) -> ReviewResult:
        prompt = REVIEW_PROMPT.format(
            source_text=source_text[:1500],
            what_happened=summary.what_happened[:300],
            why_it_matters=summary.why_it_matters[:300],
        )
        try:
            data, _ = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=256,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=ReviewResult,
            )
            return ReviewResult(**data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Reviewer LLM call failed for '%s': %s", summary.title[:60], exc)
            return ReviewResult()  # fail-open: no flags

    def _apply_flags(self, summary: ArticleSummary, result: ReviewResult) -> ArticleSummary:
        if result.inferred and summary.why_it_matters:
            summary = self._apply_inferred_prefix(summary)
        return summary

    def _apply_inferred_prefix(self, summary: ArticleSummary) -> ArticleSummary:
        if summary.why_it_matters and not summary.why_it_matters.startswith("[INFERRED]"):
            summary.why_it_matters = f"[INFERRED] {summary.why_it_matters}"
        return summary

    def _retry_extraction(
        self, summary: ArticleSummary, review_comment: str
    ) -> Optional[ArticleSummary]:
        """Re-run extraction with reviewer feedback appended to the prompt."""
        source_text = summary.source_text or summary.summary
        if not source_text:
            return None

        feedback_suffix = RETRY_SUFFIX.format(comment=review_comment)
        try:
            retried = self._extractor.extract(
                title=summary.title,
                text=source_text + feedback_suffix,
                source_name=summary.source_name,
                source_url=summary.source_url,
            )
            if retried:
                retried.score = summary.score
                retried.score_status = summary.score_status
                retried.title = summary.title
                retried.label = summary.label
                retried.author = summary.author
                retried.source_text = source_text
            return retried
        except Exception as exc:
            logger.warning("Retry extraction failed: %s", exc)
            return None

    @staticmethod
    def _make_id(url: str) -> str:
        import hashlib
        return hashlib.sha256(url.encode()).hexdigest()[:8]

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client
