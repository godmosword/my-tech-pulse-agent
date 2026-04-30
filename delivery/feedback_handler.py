"""Inline keyboard builder and callback processor for user feedback.

Callbacks:
  useful:{source_name}   → weight += 0.1 (capped at 2.0) in source_registry.yaml
  save:{item_id}         → insert into configured state store
  block_source:{name}    → set enabled: false in source_registry.yaml
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from scoring.state_store import make_state_store

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent / "sources" / "source_registry.yaml"
MAX_WEIGHT = 2.0
WEIGHT_INCREMENT = 0.1

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
