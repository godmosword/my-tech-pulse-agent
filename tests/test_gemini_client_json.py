from unittest.mock import MagicMock, patch

import pytest

from llm.gemini_client import GeminiEmptyResponseError, generate_json


def _client_with_response(resp):
    client = MagicMock()
    client.models.generate_content.return_value = resp
    return client


def test_generate_json_reads_text_even_if_parsed_is_magicmock():
    response = MagicMock()
    response.parsed = MagicMock()
    response.text = '{"entity":"OpenAI","summary":"ok"}'

    with patch("google.genai.types.GenerateContentConfig", side_effect=lambda **kw: kw):
        data, raw = generate_json(
            _client_with_response(response),
            model="m",
            system_instruction="s",
            prompt="p",
            max_output_tokens=64,
            response_schema=None,
        )

    assert data["entity"] == "OpenAI"
    assert "OpenAI" in raw


def test_generate_json_accepts_bytes_text():
    response = MagicMock()
    response.parsed = None
    response.text = b'{"score": 8.5}'

    with patch("google.genai.types.GenerateContentConfig", side_effect=lambda **kw: kw):
        data, _ = generate_json(
            _client_with_response(response),
            model="m",
            system_instruction="s",
            prompt="p",
            max_output_tokens=64,
            response_schema=None,
        )

    assert data["score"] == 8.5


def test_generate_json_reads_candidate_part_text_when_text_property_empty():
    response = MagicMock()
    response.parsed = None
    response.text = ""
    part = MagicMock()
    part.text = '{"score": 7.5}'
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response.candidates = [candidate]

    with patch("google.genai.types.GenerateContentConfig", side_effect=lambda **kw: kw):
        data, raw = generate_json(
            _client_with_response(response),
            model="m",
            system_instruction="s",
            prompt="p",
            max_output_tokens=64,
            response_schema=None,
        )

    assert data["score"] == 7.5
    assert raw == '{"score": 7.5}'


def test_generate_json_raises_empty_response_with_finish_reason():
    response = MagicMock()
    response.parsed = None
    response.text = ""
    candidate = MagicMock()
    candidate.finish_reason = "SAFETY"
    candidate.content.parts = []
    response.candidates = [candidate]

    with patch("google.genai.types.GenerateContentConfig", side_effect=lambda **kw: kw):
        with pytest.raises(GeminiEmptyResponseError) as exc_info:
            generate_json(
                _client_with_response(response),
                model="m",
                system_instruction="s",
                prompt="p",
                max_output_tokens=64,
                response_schema=None,
            )

    assert exc_info.value.finish_reason == "SAFETY"


def test_generate_json_strips_prose_preamble_before_object():
    response = MagicMock()
    response.parsed = None
    response.text = (
        "Here is the JSON requested:\n"
        '{"entity": "Acme", "summary": "ok"}'
    )

    with patch("google.genai.types.GenerateContentConfig", side_effect=lambda **kw: kw):
        data, raw = generate_json(
            _client_with_response(response),
            model="m",
            system_instruction="s",
            prompt="p",
            max_output_tokens=64,
            response_schema=None,
        )

    assert data["entity"] == "Acme"
    assert "Here is the JSON" in raw


def test_generate_json_strips_markdown_json_fence():
    response = MagicMock()
    response.parsed = None
    response.text = 'Sure.\n```json\n{"score": 9.0}\n```'

    with patch("google.genai.types.GenerateContentConfig", side_effect=lambda **kw: kw):
        data, _ = generate_json(
            _client_with_response(response),
            model="m",
            system_instruction="s",
            prompt="p",
            max_output_tokens=64,
            response_schema=None,
        )

    assert data["score"] == 9.0
