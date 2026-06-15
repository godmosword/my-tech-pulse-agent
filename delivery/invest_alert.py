"""Conservative Telegram alert for the decision brief.

Deliberately quiet: only escalates genuine position risk (``risk_up`` postures)
and imminent catalysts (within ``INVEST_ALERT_CATALYST_DAYS``). Never sends a
daily top-N buy/sell list. Opt-in via ``INVEST_ALERT_ENABLED``.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Optional

from delivery.message_formatter import escape
from delivery.pipeline_alert import resolve_alert_chat_id
from delivery.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

CATALYST_WINDOW_DAYS = 3


def _enabled() -> bool:
    return os.getenv("INVEST_ALERT_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def format_invest_alert(brief: Any, *, as_of: Optional[date] = None) -> Optional[str]:
    """Return an alert body only when something genuinely warrants attention."""
    as_of = as_of or date.today()
    window_days = int(os.getenv("INVEST_ALERT_CATALYST_DAYS", str(CATALYST_WINDOW_DAYS)))

    risk_lines: list[str] = []
    for item in getattr(brief, "material_items", []) or []:
        if getattr(item, "posture", "") != "risk_up":
            continue
        affected = "、".join(getattr(item, "affected_tickers", []) or [])
        risk_lines.append(f"• {escape(item.title)}（{escape(affected)}）")

    catalyst_lines: list[str] = []
    for cat in getattr(brief, "catalyst_watch", []) or []:
        day = str(cat.get("date") if isinstance(cat, dict) else getattr(cat, "date", ""))
        try:
            days_out = (date.fromisoformat(day[:10]) - as_of).days
        except ValueError:
            continue
        if 0 <= days_out <= window_days:
            tkr = cat.get("ticker") if isinstance(cat, dict) else getattr(cat, "ticker", "")
            note = cat.get("note") if isinstance(cat, dict) else getattr(cat, "note", "")
            catalyst_lines.append(f"• {escape(day)} {escape(str(tkr))} {escape(str(note))}")

    if not risk_lines and not catalyst_lines:
        return None

    parts = ["<b>📌 部位提醒</b>（非投資建議）"]
    if risk_lines:
        parts.append("風險升高：\n" + "\n".join(risk_lines))
    if catalyst_lines:
        parts.append("近日催化劑：\n" + "\n".join(catalyst_lines))
    return "\n\n".join(parts)


def notify_invest_brief(brief: Any, *, as_of: Optional[date] = None) -> None:
    """Best-effort; never raises. No-op unless INVEST_ALERT_ENABLED."""
    if not _enabled():
        return
    text = format_invest_alert(brief, as_of=as_of)
    if not text:
        return
    chat_id, _ = resolve_alert_chat_id()
    if not chat_id:
        logger.warning("Invest alert skipped: no alert/channel chat id configured")
        return
    try:
        bot = TelegramBot()
        if not bot.send_to_chat(text, chat_id):
            logger.error("Invest alert was not delivered to Telegram")
    except Exception as exc:  # noqa: BLE001
        logger.error("Invest alert send failed: %s", exc, exc_info=True)
