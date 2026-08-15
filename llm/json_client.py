"""OpenAI JSON generation helpers (direct api.openai.com, not OpenRouter)."""

import json
import logging
import os
import re
import time
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
OPENAI_FLASH_MODEL = os.getenv("OPENAI_FLASH_MODEL", "gpt-5.6-luna")

_RETRY_DELAYS = [2.0, 5.0]
_RETRYABLE_KEYWORDS = ("timeout", "429", "503", "rate", "quota", "unavailable", "resource_exhausted")

Tier = Literal["pro", "flash"]


class LlmEmptyResponseError(ValueError):
    """Raised when the model returns no text payload."""

    def __init__(self, finish_reason: str = ""):
        self.finish_reason = finish_reason
        message = "LLM returned an empty response"
        if finish_reason:
            message = f"{message} (finish_reason={finish_reason})"
        super().__init__(message)


class LlmJsonParseError(json.JSONDecodeError):
    """JSONDecodeError with the raw model text attached for caller-side recovery."""

    def __init__(self, inner: json.JSONDecodeError, raw_text: str):
        super().__init__(inner.msg, inner.doc, inner.pos)
        self.raw_text = raw_text


GeminiEmptyResponseError = LlmEmptyResponseError
GeminiJsonParseError = LlmJsonParseError
GEMINI_MODEL = OPENAI_MODEL
GEMINI_FLASH_MODEL = OPENAI_FLASH_MODEL


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in _RETRYABLE_KEYWORDS)


def make_client():
    """Create an OpenAI client using OPENAI_API_KEY."""
    from openai import OpenAI  # noqa: PLC0415 — lazy import for tests

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI API calls")
    request_timeout_ms = int(os.getenv("OPENAI_REQUEST_TIMEOUT_MS", "45000"))
    return OpenAI(api_key=api_key, timeout=request_timeout_ms / 1000.0)


def _prepare_json_payload(raw: str) -> str:
    """Strip markdown fences and conversational preamble before the first JSON object."""
    text = raw.strip()
    if not text:
        return text
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    brace = text.find("{")
    if brace > 0:
        text = text[brace:]
    return text


def _parse_json_from_response_text(raw: str) -> dict[str, Any]:
    """Parse JSON from model output; tolerate prose prefixes and ```json``` fences."""
    prepared = _prepare_json_payload(raw)
    blobs: list[str] = []
    if prepared.strip():
        blobs.append(prepared.strip())
    stripped = raw.strip()
    if stripped and stripped not in blobs:
        blobs.append(stripped)

    last_err: json.JSONDecodeError | None = None
    for blob in blobs:
        try:
            return json.loads(blob)
        except json.JSONDecodeError as exc:
            last_err = exc
        extracted = _extract_json_object(blob)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError as exc:
                last_err = exc
    if last_err is not None:
        raise last_err
    raise json.JSONDecodeError("No JSON object found in model response", raw[:120], 0)


def _reasoning_for_tier(tier: Tier) -> dict[str, str]:
    if tier == "flash":
        return {"effort": "none"}
    return {"mode": "pro", "effort": "medium"}


def generate_json(
    client,
    *,
    model: str,
    system_instruction: str,
    prompt: str,
    max_output_tokens: int,
    response_schema: type[BaseModel] | None = None,
    log_parse_errors: bool = True,
    tier: Tier = "pro",
) -> tuple[dict[str, Any], str]:
    """Generate a JSON object via OpenAI Responses API.

    Retries up to len(_RETRY_DELAYS) times on transient API errors (timeout, 429, 503).
    JSON parse errors are not retried here — callers handle their own parse-retry loops.
    """
    schema_hint = f" Schema name: {response_schema.__name__}." if response_schema else ""
    system = (
        f"{system_instruction}\n"
        "Return exactly one JSON object. Do not include prose, markdown, or code fences."
        f"{schema_hint}"
    )
    request = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_output_tokens": max_output_tokens,
        "reasoning": _reasoning_for_tier(tier),
        "text": {"format": {"type": "json_object"}},
    }

    last_exc: Exception | None = None
    for attempt, delay in enumerate([0.0] + _RETRY_DELAYS):
        if delay:
            logger.info("OpenAI retry attempt %d after %.1fs (model=%s)", attempt + 1, delay, model)
            time.sleep(delay)
        try:
            response = client.responses.create(**request)
            raw = _response_text(response)
            if not raw.strip():
                raise LlmEmptyResponseError(_response_finish_reason(response))
            try:
                data = _parse_json_from_response_text(raw)
                return data, raw
            except json.JSONDecodeError as parse_exc:
                if log_parse_errors:
                    logger.warning(
                        "OpenAI JSON parse error | raw_head=%s",
                        raw[:500].replace("\n", "\\n"),
                    )
                raise LlmJsonParseError(parse_exc, raw) from parse_exc
        except json.JSONDecodeError:
            raise
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise
            logger.warning(
                "OpenAI transient error (attempt %d/%d, model=%s): %s",
                attempt + 1, len(_RETRY_DELAYS) + 1, model, exc,
            )

    raise last_exc  # type: ignore[misc]


def _response_text(response: object) -> str:
    raw_obj = getattr(response, "output_text", "")
    if isinstance(raw_obj, str) and raw_obj.strip():
        return raw_obj.strip()
    if isinstance(raw_obj, (bytes, bytearray)):
        return raw_obj.decode("utf-8", errors="ignore").strip()

    parts_text: list[str] = []
    for item in getattr(response, "output", []) or []:
        for part in getattr(item, "content", []) or []:
            text = getattr(part, "text", "")
            if isinstance(text, str) and text:
                parts_text.append(text)
    return "".join(parts_text).strip()


def _response_finish_reason(response: object) -> str:
    status = getattr(response, "status", "")
    if status:
        return str(status)
    incomplete = getattr(response, "incomplete_details", None)
    reason = getattr(incomplete, "reason", "") if incomplete is not None else ""
    return str(reason or "")


def _extract_json_object(text: str) -> str:
    """Extract the first balanced JSON object from text."""
    start = text.find("{")
    if start == -1:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]

    return ""
