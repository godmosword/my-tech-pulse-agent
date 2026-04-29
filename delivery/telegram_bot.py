"""Telegram delivery for the #科技脈搏 channel."""

import asyncio
import logging
import os
from typing import Optional

from agents.earnings_agent import EarningsOutput
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput, Theme
from delivery.feedback_handler import handle_callback
from delivery.message_formatter import escape, format_earnings, format_items_digest

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096


class TelegramBot:
    def __init__(self):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
        if not token or not self._channel_id:
            logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set — delivery disabled")
            self._bot = None
            self._app = None
        else:
            # Lazy import so the cryptography chain is only triggered when a real bot is needed
            from telegram import Bot  # noqa: PLC0415
            self._bot = Bot(token=token)
            self._app = None  # populated by start_polling()

    def send_items_digest(
        self,
        summaries: list[ArticleSummary],
        total_fetched: int,
        total_after_filter: int,
        themes: Optional[list[Theme]] = None,
        market_takeaway: Optional[str] = None,
    ) -> bool:
        """Send a ranked item digest built from ArticleSummary list."""
        if not self._bot:
            logger.info("Telegram bot not configured; skipping items digest delivery")
            return False
        theme_labels = [t.theme for t in themes[:3]] if themes else None
        text = format_items_digest(
            summaries,
            total_fetched,
            total_after_filter,
            themes=theme_labels,
            market_takeaway=market_takeaway,
        )
        return self._send(text)

    def send_digest(self, digest: DigestOutput) -> bool:
        """Send a synthesizer DigestOutput (narrative format)."""
        if not self._bot:
            logger.info("Telegram bot not configured; skipping digest delivery")
            return False
        text = self._format_digest(digest)
        return self._send(text)

    def send_earnings(self, earnings: EarningsOutput) -> bool:
        if not self._bot:
            logger.info("Telegram bot not configured; skipping earnings delivery")
            return False
        text = format_earnings(earnings)
        return self._send(text)

    def start_polling(self) -> None:
        """Start long-polling for callback queries (feedback buttons).

        Runs in the current thread and blocks until interrupted.
        Call this from the scheduler process after the pipeline loop, or in
        a separate thread alongside the scheduler.
        """
        if not self._bot:
            logger.warning("Bot not configured; cannot start polling")
            return

        try:
            from telegram.ext import Application, CallbackQueryHandler  # noqa: PLC0415
        except ImportError:
            logger.error("python-telegram-bot not installed; polling unavailable")
            return

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        app = Application.builder().token(token).build()
        app.add_handler(CallbackQueryHandler(self._on_callback_query))
        logger.info("Starting Telegram callback polling …")
        app.run_polling()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send(self, text: str) -> bool:
        try:
            asyncio.run(self._async_send(text))
            return True
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return False

    async def _async_send(self, text: str) -> None:
        chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        for chunk in chunks:
            await self._bot.send_message(
                chat_id=self._channel_id,
                text=chunk,
                parse_mode="MarkdownV2",
            )

    @staticmethod
    async def _on_callback_query(update, context) -> None:
        """Handle inline keyboard button presses from users."""
        query = update.callback_query
        await query.answer()  # acknowledge immediately to remove loading spinner

        data = query.data or ""
        try:
            result = handle_callback(data)
            await query.edit_message_reply_markup(reply_markup=None)  # remove keyboard after action
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=escape(result),
                parse_mode="MarkdownV2",
            )
            logger.info("Callback handled: %s → %s", data, result)
        except Exception as exc:
            logger.error("Callback handler failed for %r: %s", data, exc)

    def _format_digest(self, digest: DigestOutput) -> str:
        lines = [
            f"*📡 科技脈搏 — {digest.date}*",
            "",
            f"*{escape(digest.headline)}*",
            "",
        ]

        if digest.themes:
            lines.append("*📌 今日主題*")
            for theme in digest.themes[:3]:
                lines.append(f"• *{escape(theme.theme)}*: {escape(theme.description)}")
            lines.append("")

        if digest.narrative:
            lines.append(escape(digest.narrative))
            lines.append("")

        if digest.contradictions:
            lines.append("*⚠️ 消息矛盾*")
            for contradiction in digest.contradictions:
                lines.append(f"• {escape(contradiction)}")
            lines.append("")

        if digest.cross_ref_count > 0:
            lines.append(f"_投資相關新聞: {digest.cross_ref_count} 篇 \\(見 \\#投資日報\\)_")

        return "\n".join(lines)

    @staticmethod
    def _escape(text: str) -> str:
        return escape(text)
