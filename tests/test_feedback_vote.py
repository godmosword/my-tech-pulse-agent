import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from delivery.feedback_handler import (
    build_vote_keyboard,
    encode_vote_callback,
    handle_vote_callback,
    item_feedback_key,
    parse_vote_callback,
)
from delivery.feedback_poller import poll_pending_feedback
from delivery.message_formatter import build_items_digest_messages
from delivery.telegram_bot import TelegramBot
from scoring.feedback_store import SQLiteFeedbackStore, feedback_doc_key, hash_telegram_user_id


def test_encode_vote_callback_within_64_bytes():
    target = "i:" + "a" * 8
    data = encode_vote_callback("up", target)
    assert len(data.encode("utf-8")) <= 64
    assert data == f"fv:1:{target}"


def test_parse_vote_callback_roundtrip():
    parsed = parse_vote_callback("fv:0:d:20260611")
    assert parsed == ("down", "digest", "20260611")


def test_build_vote_keyboard_labels():
    kb = build_vote_keyboard("d:20260611")
    row = kb["inline_keyboard"][0]
    assert row[0]["text"] == "👍 有價值"
    assert row[1]["text"] == "👎 沒價值"


def test_handle_vote_callback_overwrites_same_user_target(tmp_path):
    store = SQLiteFeedbackStore(tmp_path / "feedback.sqlite")
    with patch("delivery.feedback_handler.make_feedback_store", return_value=store):
        handle_vote_callback("fv:1:i:abc12345", user_id=42)
        handle_vote_callback("fv:0:i:abc12345", user_id=42)

    user_hash = hash_telegram_user_id(42)
    doc_key = feedback_doc_key(user_hash, "item", "abc12345")
    with store._db_path.open("rb"):
        import sqlite3

        with sqlite3.connect(store._db_path) as conn:
            row = conn.execute(
                "SELECT vote FROM feedback WHERE doc_key = ?", (doc_key,)
            ).fetchone()
    assert row is not None
    assert row[0] == "down"


def test_digest_messages_attach_feedback_targets():
    from agents.extractor_agent import ArticleSummary

    summaries = [
        ArticleSummary(
            entity="Acme",
            title="Launch",
            summary="Summary",
            what_happened="Fact",
            why_it_matters="Impact",
            category="product_launch",
            sentiment="neutral",
            confidence="high",
            score=8.0,
            source_name="example",
            source_url="https://example.com/a",
        )
    ]
    messages = build_items_digest_messages(
        summaries,
        total_fetched=1,
        total_after_filter=1,
        now=datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc),
    )
    assert messages[0].feedback_target == "d:20260611"
    card = next(m for m in messages if m.url)
    assert card.feedback_target.startswith("i:")
    assert len(card.feedback_target.split(":", 1)[1]) == 8


def test_telegram_build_digest_reply_markup_merges_vote_and_url():
    msg = SimpleNamespace(
        feedback_target="i:abc12345",
        url="https://example.com/a",
    )
    markup = TelegramBot._build_digest_reply_markup(msg)
    assert markup is not None
    assert len(markup.inline_keyboard) == 2
    assert markup.inline_keyboard[0][0].callback_data.startswith("fv:")
    assert markup.inline_keyboard[1][0].url == "https://example.com/a"


def test_poll_pending_feedback_processes_callbacks(tmp_path):
    from delivery.feedback_poller import _poll_pending_feedback_async

    store = SQLiteFeedbackStore(tmp_path / "feedback.sqlite")
    callback = SimpleNamespace(
        data="fv:1:d:20260611",
        from_user=SimpleNamespace(id=99),
        answer=AsyncMock(),
    )
    update = SimpleNamespace(update_id=10, callback_query=callback)

    mock_bot = MagicMock()
    mock_bot.get_updates = AsyncMock(return_value=[update])

    with (
        patch("delivery.feedback_poller.make_feedback_store", return_value=store),
        patch("delivery.feedback_handler.make_feedback_store", return_value=store),
        patch("telegram.Bot", return_value=mock_bot),
    ):
        processed = asyncio.run(_poll_pending_feedback_async("test-token"))

    assert processed == 1
    callback.answer.assert_awaited_once()
    assert store.get_update_offset() == 11
    user_hash = hash_telegram_user_id(99)
    doc_key = feedback_doc_key(user_hash, "digest", "20260611")
    import sqlite3

    with sqlite3.connect(store._db_path) as conn:
        row = conn.execute(
            "SELECT vote FROM feedback WHERE doc_key = ?", (doc_key,)
        ).fetchone()
    assert row == ("up",)


def test_poll_pending_feedback_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    with patch(
        "delivery.feedback_poller.asyncio.run",
        side_effect=RuntimeError("network down"),
    ):
        assert poll_pending_feedback() == 0


def test_item_feedback_key_stable():
    key_a = item_feedback_key("https://example.com/x")
    key_b = item_feedback_key("https://example.com/x")
    assert key_a == key_b
    assert key_a.startswith("i:")
