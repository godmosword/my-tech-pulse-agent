"""Batch-fetch Telegram callback updates during one-shot pipeline runs."""

from __future__ import annotations

import asyncio
import logging
import os

from delivery.feedback_handler import handle_vote_callback, parse_vote_callback
from scoring.feedback_store import make_feedback_store

logger = logging.getLogger(__name__)


def poll_pending_feedback() -> int:
    """Pull unprocessed callback updates via getUpdates; never raises."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        logger.info("Telegram bot not configured; skipping feedback poll")
        return 0
    try:
        return asyncio.run(_poll_pending_feedback_async(token))
    except Exception as exc:
        logger.error("Telegram feedback poll failed: %s", exc, exc_info=True)
        return 0


async def _poll_pending_feedback_async(token: str) -> int:
    from telegram import Bot  # noqa: PLC0415

    bot = Bot(token=token)
    store = make_feedback_store()
    offset = store.get_update_offset()
    try:
        updates = await bot.get_updates(
            offset=offset,
            timeout=0,
            allowed_updates=["callback_query"],
        )
    except Exception as exc:
        logger.error("Telegram getUpdates failed: %s", exc, exc_info=True)
        return 0

    if not updates:
        return 0

    processed = 0
    next_offset = offset
    for update in updates:
        next_offset = max(next_offset, update.update_id + 1)
        query = update.callback_query
        if not query or not query.data:
            continue
        if parse_vote_callback(query.data) is None:
            try:
                await query.answer()
            except Exception as exc:
                logger.warning("answerCallbackQuery skipped for legacy callback: %s", exc)
            continue

        user_id = query.from_user.id if query.from_user else 0
        try:
            ack = handle_vote_callback(query.data, user_id=user_id)
            await query.answer(ack)
            processed += 1
            logger.info("Recorded Telegram feedback vote: %s (user hash only)", query.data)
        except Exception as exc:
            logger.error("Failed to process vote callback %r: %s", query.data, exc, exc_info=True)
            try:
                await query.answer("回饋暫時無法記錄，請稍後再試", show_alert=False)
            except Exception as answer_exc:
                logger.warning("answerCallbackQuery after vote failure failed: %s", answer_exc)

    try:
        store.set_update_offset(next_offset)
    except Exception as exc:
        logger.error("Failed to persist Telegram update offset %s: %s", next_offset, exc)

    return processed
