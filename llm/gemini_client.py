"""Gemini JSON generation helpers."""

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from google import genai as _genai

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")


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


def generate_json(
    client,
    *,
    model: str,
    system_instruction: str,
    prompt: str,
    max_output_tokens: int,
    response_schema: type[BaseModel] | None = None,
) -> tuple[dict[str, Any], str]:
    """Generate a JSON object with Gemini and return parsed data plus raw text."""
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
    if hasattr(types, "ThinkingConfig") and hasattr(types, "ThinkingLevel"):
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.LOW
        )

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

    raw_obj = getattr(response, "text", "")
    if isinstance(raw_obj, str):
        raw = raw_obj.strip()
    elif isinstance(raw_obj, (bytes, bytearray)):
        raw = raw_obj.decode("utf-8", errors="ignore").strip()
    else:
        raw = ""
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        extracted = _extract_json_object(raw)
        if extracted:
            return json.loads(extracted), raw
        logger.warning("Gemini JSON parse error | raw=%s", raw[:200])
        raise


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
