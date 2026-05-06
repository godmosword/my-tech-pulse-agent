"""Gemini JSON generation helpers."""

import json
import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from google import genai as _genai

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")

# Retry delays for transient Gemini API errors (seconds between attempts)
_RETRY_DELAYS = [2.0, 5.0]
_RETRYABLE_KEYWORDS = ("timeout", "429", "503", "rate", "quota", "unavailable", "resource_exhausted")


class GeminiEmptyResponseError(ValueError):
    """Raised when Gemini returns no text payload for a generation request."""

    def __init__(self, finish_reason: str = ""):
        self.finish_reason = finish_reason
        message = "Gemini returned an empty response"
        if finish_reason:
            message = f"{message} (finish_reason={finish_reason})"
        super().__init__(message)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in _RETRYABLE_KEYWORDS)


def make_client():
    """Create a Gemini client using GEMINI_API_KEY."""
    from google import genai  # noqa: PLC0415 — lazy to avoid cryptography/cffi crash in tests
    from google.genai import types  # noqa: PLC0415 — lazy import
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini API calls")
    request_timeout_ms = int(os.getenv("GEMINI_REQUEST_TIMEOUT_MS", "45000"))
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=request_timeout_ms),
    )


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


def generate_json(
    client,
    *,
    model: str,
    system_instruction: str,
    prompt: str,
    max_output_tokens: int,
    response_schema: type[BaseModel] | None = None,
    log_parse_errors: bool = True,
) -> tuple[dict[str, Any], str]:
    """Generate a JSON object with Gemini and return parsed data plus raw text.

    Retries up to len(_RETRY_DELAYS) times on transient API errors (timeout, 429, 503).
    JSON parse errors are not retried here — callers handle their own parse-retry loops.
    """
    from google.genai import types  # noqa: PLC0415 — lazy import
    config_kwargs = {
        "system_instruction": (
            f"{system_instruction}\n"
            "Return exactly one JSON object. Do not include prose, markdown, or code fences."
        ),
        "max_output_tokens": max_output_tokens,
        "temperature": 0,
        "response_mime_type": "application/json",
        "response_schema": response_schema,
    }
    # Thinking + JSON can steal output budget on Flash; disable by default for flash models.
    _no_thinking = (
        os.getenv("GEMINI_DISABLE_THINKING_FOR_FLASH", "1") == "1" and "flash" in model.lower()
    )
    if (
        not _no_thinking
        and hasattr(types, "ThinkingConfig")
        and hasattr(types, "ThinkingLevel")
    ):
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.LOW
        )

    last_exc: Exception | None = None
    for attempt, delay in enumerate([0.0] + _RETRY_DELAYS):
        if delay:
            logger.info("Gemini retry attempt %d after %.1fs (model=%s)", attempt + 1, delay, model)
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, BaseModel):
                return parsed.model_dump(), json.dumps(parsed.model_dump(), ensure_ascii=False)
            if isinstance(parsed, dict):
                return parsed, json.dumps(parsed, ensure_ascii=False)

            raw = _response_text(response)
            if not raw.strip():
                raise GeminiEmptyResponseError(_response_finish_reason(response))
            try:
                data = _parse_json_from_response_text(raw)
                return data, raw
            except json.JSONDecodeError:
                if log_parse_errors:
                    logger.warning(
                        "Gemini JSON parse error | raw_head=%s",
                        raw[:500].replace("\n", "\\n"),
                    )
                raise  # JSON parse errors propagate immediately — no point retrying
        except json.JSONDecodeError:
            raise
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise
            logger.warning(
                "Gemini transient error (attempt %d/%d, model=%s): %s",
                attempt + 1, len(_RETRY_DELAYS) + 1, model, exc,
            )

    raise last_exc  # type: ignore[misc]


def _response_text(response: object) -> str:
    """Return text from Gemini responses, including candidate parts when available."""
    raw_obj = getattr(response, "text", "")
    if isinstance(raw_obj, str) and raw_obj.strip():
        return raw_obj.strip()
    if isinstance(raw_obj, (bytes, bytearray)):
        return raw_obj.decode("utf-8", errors="ignore").strip()

    parts_text: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", "")
            if isinstance(text, str) and text:
                parts_text.append(text)
    return "".join(parts_text).strip()


def _response_finish_reason(response: object) -> str:
    """Return the first Gemini candidate finish reason, if available."""
    for candidate in getattr(response, "candidates", []) or []:
        finish_reason = getattr(candidate, "finish_reason", "")
        if finish_reason:
            name = getattr(finish_reason, "name", "")
            return str(name or finish_reason)
    return ""


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
