"""Inline keyboard builder and callback processor for user feedback.

Callbacks:
  fv:{1|0}:{d|i}:{id}    → digest/item vote (👍/👎), persisted to feedback store
  useful:{source_name}   → weight += 0.1 (capped at 2.0) in source_registry.yaml
  save:{item_id}         → insert into configured state store
  block_source:{name}    → set enabled: false in source_registry.yaml
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from scoring.feedback_store import TargetType, VoteValue, make_feedback_store
from scoring.state_store import make_state_store

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent / "sources" / "source_registry.yaml"
MAX_WEIGHT = 2.0
WEIGHT_INCREMENT = 0.1
VOTE_CALLBACK_PREFIX = "fv"
TARGET_TYPE_CODES = {"d": "digest", "i": "item"}
TARGET_TYPE_TO_CODE = {v: k for k, v in TARGET_TYPE_CODES.items()}

def encode_vote_callback(vote: VoteValue, target_key: str) -> str:
    """Build Telegram callback_data for a digest/item vote (≤64 bytes)."""
    vote_bit = "1" if vote == "up" else "0"
    return f"{VOTE_CALLBACK_PREFIX}:{vote_bit}:{target_key}"


def build_vote_keyboard(target_key: str) -> dict:
    """Return InlineKeyboardMarkup-compatible dict with 👍/👎 vote buttons."""
    return {
        "inline_keyboard": [[
            {"text": "👍 有價值", "callback_data": encode_vote_callback("up", target_key)},
            {"text": "👎 沒價值", "callback_data": encode_vote_callback("down", target_key)},
        ]]
    }


def parse_vote_callback(data: str) -> tuple[VoteValue, TargetType, str] | None:
    """Parse `fv:{1|0}:{d|i}:{id}` into (vote, target_type, target_id)."""
    if not data.startswith(f"{VOTE_CALLBACK_PREFIX}:"):
        return None
    parts = data.split(":", 3)
    if len(parts) != 4:
        return None
    _, vote_bit, type_code, target_id = parts
    if vote_bit not in {"0", "1"} or type_code not in TARGET_TYPE_CODES or not target_id:
        return None
    vote: VoteValue = "up" if vote_bit == "1" else "down"
    target_type: TargetType = TARGET_TYPE_CODES[type_code]  # type: ignore[assignment]
    return vote, target_type, target_id


def digest_feedback_key(now: datetime | None = None) -> str:
    from delivery.message_formatter import digest_feedback_date_key

    return f"d:{digest_feedback_date_key(now)}"


def item_feedback_key(source_url: str, *, fallback: str = "") -> str:
    from delivery.message_formatter import item_feedback_id

    item_id = item_feedback_id(source_url, fallback=fallback)
    if not item_id:
        return ""
    return f"i:{item_id}"


def handle_vote_callback(
    data: str,
    *,
    user_id: int,
    voted_at: datetime | None = None,
) -> str:
    """Persist a vote callback and return a short acknowledgement string."""
    parsed = parse_vote_callback(data)
    if not parsed:
        return "Unknown vote callback."
    vote, target_type, target_id = parsed
    from scoring.feedback_store import hash_telegram_user_id

    store = make_feedback_store()
    store.save_vote(
        target_id=target_id,
        target_type=target_type,
        vote=vote,
        user_id_hash=hash_telegram_user_id(user_id),
        voted_at=voted_at or datetime.now(timezone.utc),
    )
    return "已記錄回饋，謝謝！"


def build_keyboard(item_id: str, source_name: str) -> dict:
    """Return an InlineKeyboardMarkup-compatible dict with feedback buttons.

    Compatible with python-telegram-bot's InlineKeyboardMarkup/InlineKeyboardButton.
    Returns a plain dict so it can be built without importing telegram at call time.
    """
    return {
        "inline_keyboard": [[
            {"text": "👍 有用", "callback_data": f"useful:{source_name}"},
            {"text": "🔖 收藏", "callback_data": f"save:{item_id}"},
            {"text": "🚫 封鎖來源", "callback_data": f"block_source:{source_name}"},
        ]]
    }


def parse_callback(data: str) -> tuple[str, str]:
    """Parse callback_data into (action, payload).

    Returns ("unknown", data) for unrecognised formats.
    """
    if ":" in data:
        action, _, payload = data.partition(":")
        return action, payload
    return "unknown", data


def handle_callback(data: str, db_path: Optional[Path] = None) -> str:
    """Dispatch a callback and return a human-readable result string."""
    action, payload = parse_callback(data)
    if action == "useful":
        return _handle_useful(payload)
    if action == "save":
        return _handle_save(payload, db_path)
    if action == "block_source":
        return _handle_block(payload)
    return f"Unknown callback action: {action}"


# ---------------------------------------------------------------------------
# Private handlers
# ---------------------------------------------------------------------------

def _handle_useful(source_name: str) -> str:
    updated = _update_registry_field(source_name, "weight", _increment_weight)
    if updated:
        return f"Source '{source_name}' weight increased."
    return f"Source '{source_name}' not found in registry."


def _handle_save(item_id: str, db_path: Optional[Path] = None) -> str:
    store = make_state_store(Path(db_path) if db_path is not None else None)
    store.save_item(item_id, datetime.now(timezone.utc))
    return f"Item '{item_id}' saved."


def _handle_block(source_name: str) -> str:
    updated = _update_registry_field(source_name, "enabled", lambda _: False)
    if updated:
        return f"Source '{source_name}' blocked (enabled=false)."
    return f"Source '{source_name}' not found in registry."


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def _increment_weight(current: float) -> float:
    return min(round(current + WEIGHT_INCREMENT, 2), MAX_WEIGHT)


def _update_registry_field(source_name: str, field: str, transform) -> bool:
    """Load registry YAML, apply transform to field, save back. Returns True if found."""
    try:
        with open(REGISTRY_PATH) as f:
            data = yaml.safe_load(f)

        found = False
        for entry in data.get("sources", []):
            if entry.get("name") == source_name:
                current = entry.get(field, 1.0 if field == "weight" else True)
                entry[field] = transform(current)
                found = True
                break

        if found:
            with open(REGISTRY_PATH, "w") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            logger.info("Registry updated: %s.%s", source_name, field)

        return found
    except Exception as exc:
        logger.error("Failed to update registry for %s.%s: %s", source_name, field, exc)
        return False
