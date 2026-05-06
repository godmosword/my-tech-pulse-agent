"""Stage 2.5 — Reviewer Agent: fact-grounding check and quality gate.

Sits between ExtractorAgent and SynthesizerAgent. Checks three things:
1. fact_error  — what_happened contains numbers not present verbatim in source text
2. inferred    — why_it_matters makes causal claims with no source basis → prepend [INFERRED]
3. needs_retry — why_it_matters is generic with no specific entity or mechanism

Additionally: if what_happened is shorter than MIN_WHAT_HAPPENED_CHARS (default 45), the pipeline
sets needs_retry=True for one grounded extraction retry (same budget as LLM-flagged retry).

On needs_retry=True: ExtractorAgent reruns once with review_comment as feedback.
After max_retry=1: approve with confidence="low" regardless of output quality.
"""

import json
import logging
import os
import re
from typing import Optional

from pydantic import BaseModel

from agents.extractor_agent import ArticleSummary, ExtractorAgent
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL
REVIEWER_MAX_OUTPUT_TOKENS = int(os.getenv("REVIEWER_MAX_OUTPUT_TOKENS", "1024"))

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
   Also true if what_happened is extremely thin or vague while the source excerpt clearly contains
   concrete anchors you could quote. false otherwise.

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


def _recover_review_result_from_partial_json(text: str) -> Optional[ReviewResult]:
    """When Gemini truncates mid-JSON, recover booleans (and review_comment if complete enough).

    Requires both ``fact_error`` and ``inferred`` literals — matches reviewer prompt field order
    and avoids guessing when output stops after the first field only.
    """
    if not text.strip():
        return None
    fe_m = re.search(r'"fact_error"\s*:\s*(true|false)', text, re.I)
    inf_m = re.search(r'"inferred"\s*:\s*(true|false)', text, re.I)
    if not fe_m or not inf_m:
        return None
    nr_m = re.search(r'"needs_retry"\s*:\s*(true|false)', text, re.I)
    fact_error = fe_m.group(1).lower() == "true"
    inferred = inf_m.group(1).lower() == "true"
    needs_retry = nr_m.group(1).lower() == "true" if nr_m else False

    review_comment: Optional[str] = None
    if re.search(r'"review_comment"\s*:\s*null\b', text):
        review_comment = None
    else:
        cm = re.search(r'"review_comment"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if cm:
            review_comment = (
                cm.group(1).replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            )

    return ReviewResult(
        fact_error=fact_error,
        inferred=inferred,
        needs_retry=needs_retry,
        review_comment=review_comment,
    )


class ReviewerOutput(BaseModel):
    item_id: str
    approved: bool
    needs_retry: bool
    fact_error: bool
    inferred: bool
    review_comment: Optional[str]
    final_output: Optional[ArticleSummary]
    extract_retry_used: bool = False


class ReviewerAgent:
    """Reviews ArticleSummary outputs for hallucination and quality before synthesis."""

    def __init__(self):
        self._client = None
        self._extractor = ExtractorAgent()

    def review(self, summary: ArticleSummary, retry_count: int = 0) -> ReviewerOutput:
        item_id = self._make_id(summary.source_url)
        source_text = summary.source_text or summary.summary

        result = self._call_reviewer(summary, source_text)

        if not result.fact_error:
            min_wh = int(os.getenv("MIN_WHAT_HAPPENED_CHARS", "45"))
            wh = (summary.what_happened or "").strip()
            if not result.needs_retry and len(wh) < min_wh:
                result = result.model_copy(
                    update={
                        "needs_retry": True,
                        "review_comment": (
                            "what_happened is too brief; add concrete subjects, numbers, or dates "
                            "that appear verbatim in the source only."
                        ),
                    }
                )

        if result.fact_error:
            logger.warning(
                "fact_error flagged for '%s' — numbers may not match source",
                summary.title[:60],
            )
            out = ReviewerOutput(
                item_id=item_id,
                approved=True,  # still deliver, but confidence degrades
                needs_retry=False,
                fact_error=True,
                inferred=result.inferred,
                review_comment=result.review_comment,
                final_output=self._apply_flags(summary, result),
                extract_retry_used=False,
            )
            self._log_review_metrics(out)
            return out

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
                out = ReviewerOutput(
                    item_id=item_id,
                    approved=True,
                    needs_retry=False,
                    fact_error=False,
                    inferred=False,
                    review_comment=result.review_comment,
                    final_output=retried,
                    extract_retry_used=True,
                )
                self._log_review_metrics(out)
                return out
            # retry produced nothing — fall through to approve with low confidence
            summary.confidence = "low"

        if result.needs_retry:
            summary.confidence = "low"

        out = ReviewerOutput(
            item_id=item_id,
            approved=True,
            needs_retry=False,
            fact_error=False,
            inferred=result.inferred,
            review_comment=result.review_comment if result.needs_retry else None,
            final_output=self._apply_flags(summary, result),
            extract_retry_used=False,
        )
        self._log_review_metrics(out)
        return out

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
                    extract_retry_used=False,
                ))
        return outputs

    @staticmethod
    def _log_review_metrics(output: ReviewerOutput) -> None:
        summary = output.final_output
        if summary is None:
            return
        logger.info(
            "summary_metrics item_id=%s len_wh=%d len_why=%d confidence=%s extract_retry_used=%s fact_error=%s",
            output.item_id,
            len((summary.what_happened or "").strip()),
            len((summary.why_it_matters or "").strip()),
            summary.confidence,
            output.extract_retry_used,
            output.fact_error,
        )

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
                max_output_tokens=REVIEWER_MAX_OUTPUT_TOKENS,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=ReviewResult,
            )
            return ReviewResult(**data)
        except json.JSONDecodeError as exc:
            raw = getattr(exc, "raw_text", "") or ""
            recovered = _recover_review_result_from_partial_json(raw)
            if recovered is not None:
                logger.info(
                    "Reviewer recovered partial JSON (truncated Gemini output) title=%s",
                    summary.title[:60],
                )
                return recovered
            logger.warning("Reviewer LLM parse failed for '%s': %s", summary.title[:60], exc)
            return ReviewResult()  # fail-open: no flags
        except Exception as exc:
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
