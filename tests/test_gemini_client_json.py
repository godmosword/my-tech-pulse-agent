from unittest.mock import MagicMock, patch

from llm.gemini_client import generate_json


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
