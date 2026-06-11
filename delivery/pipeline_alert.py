"""Telegram alerts for unhandled pipeline failures."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from delivery.message_formatter import escape
from delivery.telegram_bot import TelegramBot
from pipeline.runtime_config import tech_pulse_env

logger = logging.getLogger(__name__)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
EXCEPTION_MESSAGE_MAX_CHARS = 200


def resolve_alert_chat_id() -> tuple[str, bool]:
    """Return (chat_id, used_channel_fallback)."""
    alert_chat_id = (os.environ.get("TELEGRAM_ALERT_CHAT_ID") or "").strip()
    if alert_chat_id:
        return alert_chat_id, False
    channel_id = (os.environ.get("TELEGRAM_CHANNEL_ID") or "").strip()
    return channel_id, True


def format_pipeline_failure_alert(pipeline_name: str, exc: BaseException) -> str:
    env_label = tech_pulse_env()
    exc_type = type(exc).__name__
    exc_message = escape(str(exc)[:EXCEPTION_MESSAGE_MAX_CHARS])
    timestamp = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    pipeline = escape(pipeline_name)
    return (
        f"<b>🚨 Pipeline 失敗告警</b>\n"
        f"環境: {escape(env_label)}\n"
        f"管線: {pipeline}\n"
        f"例外: {escape(exc_type)}\n"
        f"訊息: {exc_message}\n"
        f"時間: {escape(timestamp)}"
    )


def notify_pipeline_failure(pipeline_name: str, exc: BaseException) -> None:
    """Best-effort Telegram alert; never raises."""
    chat_id, used_fallback = resolve_alert_chat_id()
    if not chat_id:
        logger.warning(
            "Pipeline failure alert skipped: TELEGRAM_ALERT_CHAT_ID and TELEGRAM_CHANNEL_ID unset"
        )
        return

    if used_fallback:
        logger.info(
            "TELEGRAM_ALERT_CHAT_ID not set; sending pipeline failure alert to TELEGRAM_CHANNEL_ID"
        )

    text = format_pipeline_failure_alert(pipeline_name, exc)
    try:
        bot = TelegramBot()
        if not bot.send_to_chat(text, chat_id):
            logger.error("Pipeline failure alert was not delivered to Telegram")
    except Exception as alert_exc:
        logger.error("Pipeline failure alert send failed: %s", alert_exc, exc_info=True)
