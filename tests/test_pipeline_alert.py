from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from delivery import pipeline_alert


def test_resolve_alert_chat_id_prefers_alert_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "-100alert")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-100channel")

    chat_id, used_fallback = pipeline_alert.resolve_alert_chat_id()

    assert chat_id == "-100alert"
    assert used_fallback is False


def test_resolve_alert_chat_id_falls_back_to_channel(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALERT_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-100channel")

    chat_id, used_fallback = pipeline_alert.resolve_alert_chat_id()

    assert chat_id == "-100channel"
    assert used_fallback is True


def test_format_pipeline_failure_alert_includes_fields(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_ENV", "staging")
    fixed_now = datetime(2026, 6, 11, 15, 30, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    with patch("delivery.pipeline_alert.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        text = pipeline_alert.format_pipeline_failure_alert(
            "tech-pulse",
            RuntimeError("x" * 250),
        )

    assert "🚨 Pipeline 失敗告警" in text
    assert "環境: staging" in text
    assert "管線: tech-pulse" in text
    assert "例外: RuntimeError" in text
    assert "x" * 200 in text
    assert "x" * 201 not in text
    assert "2026-06-11 15:30:00" in text


def test_notify_pipeline_failure_sends_to_alert_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "-100alert")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-100channel")
    mock_bot = MagicMock()
    mock_bot.send_to_chat.return_value = True

    with patch("delivery.pipeline_alert.TelegramBot", return_value=mock_bot) as bot_cls:
        pipeline_alert.notify_pipeline_failure("tech-pulse", ValueError("boom"))

    bot_cls.assert_called_once()
    mock_bot.send_to_chat.assert_called_once()
    sent_text, chat_id = mock_bot.send_to_chat.call_args.args
    assert chat_id == "-100alert"
    assert "ValueError" in sent_text
    assert "boom" in sent_text


def test_notify_pipeline_failure_logs_fallback_and_uses_channel(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_ALERT_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-100channel")
    mock_bot = MagicMock()
    mock_bot.send_to_chat.return_value = True

    with caplog.at_level("INFO"):
        with patch("delivery.pipeline_alert.TelegramBot", return_value=mock_bot):
            pipeline_alert.notify_pipeline_failure("tech-pulse", RuntimeError("oops"))

    assert "TELEGRAM_ALERT_CHAT_ID not set" in caplog.text
    _, chat_id = mock_bot.send_to_chat.call_args.args
    assert chat_id == "-100channel"


def test_notify_pipeline_failure_send_error_does_not_raise(monkeypatch, caplog):
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "-100alert")
    mock_bot = MagicMock()
    mock_bot.send_to_chat.side_effect = OSError("network down")

    with caplog.at_level("ERROR"):
        with patch("delivery.pipeline_alert.TelegramBot", return_value=mock_bot):
            pipeline_alert.notify_pipeline_failure("tech-pulse", RuntimeError("root cause"))

    assert "Pipeline failure alert send failed" in caplog.text


def test_notify_pipeline_failure_skips_when_no_chat_ids(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_ALERT_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)

    with caplog.at_level("WARNING"):
        with patch("delivery.pipeline_alert.TelegramBot") as bot_cls:
            pipeline_alert.notify_pipeline_failure("tech-pulse", RuntimeError("boom"))

    bot_cls.assert_not_called()
    assert "Pipeline failure alert skipped" in caplog.text
