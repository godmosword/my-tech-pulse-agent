from unittest.mock import MagicMock

import pytest

from llm.json_client import LlmEmptyResponseError, generate_json


def _client_with_text(text: str | bytes, *, status: str = "completed", reason: str = ""):
    response = MagicMock()
    response.output_text = text
    response.status = status
    response.output = []
    incomplete = MagicMock()
    incomplete.reason = reason
    response.incomplete_details = incomplete if reason else None
    client = MagicMock()
    client.responses.create.return_value = response
    return client


def test_generate_json_reads_output_text():
    data, raw = generate_json(
        _client_with_text('{"entity":"OpenAI","summary":"ok"}'),
        model="m",
        system_instruction="s",
        prompt="p",
        max_output_tokens=64,
        response_schema=None,
    )

    assert data["entity"] == "OpenAI"
    assert "OpenAI" in raw


def test_generate_json_accepts_bytes_text():
    data, _ = generate_json(
        _client_with_text(b'{"score": 8.5}'),
        model="m",
        system_instruction="s",
        prompt="p",
        max_output_tokens=64,
        response_schema=None,
    )

    assert data["score"] == 8.5


def test_generate_json_raises_empty_response_with_finish_reason():
    with pytest.raises(LlmEmptyResponseError) as exc_info:
        generate_json(
            _client_with_text("", status="incomplete", reason="SAFETY"),
            model="m",
            system_instruction="s",
            prompt="p",
            max_output_tokens=64,
            response_schema=None,
        )

    assert exc_info.value.finish_reason in {"incomplete", "SAFETY"}


def test_generate_json_strips_prose_preamble_before_object():
    data, raw = generate_json(
        _client_with_text('Here is the JSON requested:\n{"entity": "Acme", "summary": "ok"}'),
        model="m",
        system_instruction="s",
        prompt="p",
        max_output_tokens=64,
        response_schema=None,
    )

    assert data["entity"] == "Acme"
    assert "Here is the JSON" in raw


def test_generate_json_strips_markdown_json_fence():
    data, _ = generate_json(
        _client_with_text('Sure.\n```json\n{"score": 9.0}\n```'),
        model="m",
        system_instruction="s",
        prompt="p",
        max_output_tokens=64,
        response_schema=None,
    )

    assert data["score"] == 9.0


def test_generate_json_flash_sets_reasoning_none():
    client = _client_with_text('{"score": 1}')
    generate_json(
        client,
        model="gpt-5.6-luna",
        system_instruction="s",
        prompt="p",
        max_output_tokens=64,
        tier="flash",
    )
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["reasoning"] == {"effort": "none"}


def test_generate_json_pro_sets_reasoning_pro_medium():
    client = _client_with_text('{"score": 1}')
    generate_json(
        client,
        model="gpt-5.6-luna",
        system_instruction="s",
        prompt="p",
        max_output_tokens=64,
        tier="pro",
    )
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["reasoning"] == {"mode": "pro", "effort": "medium"}
