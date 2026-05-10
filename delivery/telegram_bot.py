"""Telegram delivery for the #科技脈搏 channel."""

import asyncio
import logging
import os
from typing import Optional

from agents.earnings_agent import EarningsOutput
from agents.deep_insight_agent import InsightBrief
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput, StoryInsight, Theme
from delivery.feedback_handler import handle_callback
from delivery.message_formatter import escape, format_earnings, format_insight_brief, format_items_digest

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
TELEGRAM_CHUNK_DELAY_MS = int(os.getenv("TELEGRAM_CHUNK_DELAY_MS", "500"))


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
        headline: Optional[str] = None,
        narrative_excerpt: Optional[str] = None,
        story_insights: Optional[list[StoryInsight]] = None,
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
            headline=headline,
            narrative_excerpt=narrative_excerpt,
            story_insights=story_insights,
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

    def send_deep_brief(self, brief: InsightBrief) -> bool:
        if not self._bot:
            logger.info("Telegram bot not configured; skipping deep brief delivery")
            return False
        return self._send(format_insight_brief(brief))

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
        """Send message with smart chunking at theme boundaries to preserve formatting."""
        chunks = self._smart_chunk_text(text)

        for i, chunk in enumerate(chunks):
            if not self._validate_markdown_boundaries(chunk):
                logger.warning(
                    "Chunk %d has unmatched markdown escapes; may render incorrectly",
                    i,
                )

            try:
                await self._bot.send_message(
                    chat_id=self._channel_id,
                    text=chunk,
                    parse_mode="HTML",
                )
                logger.info("Sent digest chunk %d/%d (%d chars)", i + 1, len(chunks), len(chunk))

                if i < len(chunks) - 1:
                    await asyncio.sleep(TELEGRAM_CHUNK_DELAY_MS / 1000.0)
            except Exception as exc:
                logger.error("Chunk %d delivery failed: %s", i, exc)
                raise

    @staticmethod
    def _smart_chunk_text(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
        """Split text by theme boundaries, or by character count if needed.

        Prefers splitting at newlines (theme boundaries), but falls back to
        character-based splitting for lines exceeding max_length.
        """
        if not text:
            return [""]

        lines = text.split("\n")
        chunks = []
        current = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1
            new_total = current_len + line_len

            if len(line) > max_length:
                if current:
                    chunks.append("\n".join(current))
                    current = []
                    current_len = 0
                for i in range(0, len(line), max_length):
                    chunks.append(line[i : i + max_length])
            elif current and new_total > max_length:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len = new_total

        if current:
            chunks.append("\n".join(current))

        return chunks

    @staticmethod
    def _validate_markdown_boundaries(text: str) -> bool:
        """Check if text has unmatched backslash escapes at boundaries."""
        if not text:
            return True
        trailing = len(text) - len(text.rstrip("\\"))
        return trailing % 2 == 0

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
                parse_mode="HTML",
            )
            logger.info("Callback handled: %s → %s", data, result)
        except Exception as exc:
            logger.error("Callback handler failed for %r: %s", data, exc)

    def _format_digest(self, digest: DigestOutput) -> str:
        lines = [
            f"<b>📡 科技脈搏 — {escape(digest.date)}</b>",
            "",
            f"<b>{escape(digest.headline)}</b>",
            "",
        ]

        if digest.themes:
            lines.append("<b>📌 今日主題</b>")
            for theme in digest.themes[:3]:
                lines.append(f"• <b>{escape(theme.theme)}</b>: {escape(theme.description)}")
            lines.append("")

        if digest.narrative:
            lines.append(escape(digest.narrative))
            lines.append("")

        if digest.contradictions:
            lines.append("<b>⚠️ 消息矛盾</b>")
            for contradiction in digest.contradictions:
                lines.append(f"• {escape(contradiction)}")
            lines.append("")

        if digest.cross_ref_count > 0:
            lines.append(f"<i>投資相關新聞: {digest.cross_ref_count} 篇 (見 #投資日報)</i>")

        return "\n".join(lines)

    @staticmethod
    def _escape(text: str) -> str:
        return escape(text)
