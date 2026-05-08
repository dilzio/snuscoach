"""Tests for chat thread persistence: DB layer.

Verifies:
- get_or_create_thread creates a new row and returns its id
- get_or_create_thread returns the same id on a second call for the same key
- add_chat_message stores messages and updates thread.updated_at
- list_chat_messages returns messages in chronological order
- list_chat_messages returns [] for an unknown thread
- list_chat_messages returns [] gracefully when the tables are absent
"""

from snuscoach import db


def test_get_or_create_thread_creates_new_row(temp_db):
    tid = db.get_or_create_thread("home-nudge-2026-05-08")
    assert isinstance(tid, int)
    assert tid > 0


def test_get_or_create_thread_returns_same_id_on_second_call(temp_db):
    tid1 = db.get_or_create_thread("home-nudge-2026-05-08")
    tid2 = db.get_or_create_thread("home-nudge-2026-05-08")
    assert tid1 == tid2


def test_get_or_create_thread_different_keys_get_different_ids(temp_db):
    tid1 = db.get_or_create_thread("home-nudge-2026-05-08")
    tid2 = db.get_or_create_thread("home-nudge-2026-05-09")
    assert tid1 != tid2


def test_add_chat_message_round_trip(temp_db):
    tid = db.get_or_create_thread("test-thread")
    mid = db.add_chat_message(tid, "user", "Hello coach")
    assert isinstance(mid, int)

    rows = db.list_chat_messages(tid)
    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "Hello coach"


def test_list_chat_messages_returns_in_order(temp_db):
    tid = db.get_or_create_thread("test-thread")
    db.add_chat_message(tid, "user", "First")
    db.add_chat_message(tid, "assistant", "Second")
    db.add_chat_message(tid, "user", "Third")

    rows = db.list_chat_messages(tid)
    assert [r["content"] for r in rows] == ["First", "Second", "Third"]
    assert [r["role"] for r in rows] == ["user", "assistant", "user"]


def test_list_chat_messages_returns_empty_for_unknown_thread(temp_db):
    rows = db.list_chat_messages(9999)
    assert rows == []


def test_list_chat_messages_graceful_if_table_absent(temp_db_path):
    """list_chat_messages returns [] gracefully if chat_messages table doesn't exist."""
    result = db.list_chat_messages(1)
    assert result == []


def test_add_chat_message_updates_thread_updated_at(temp_db):
    import time
    tid = db.get_or_create_thread("test-thread")
    with db.connect() as conn:
        before = conn.execute(
            "SELECT updated_at FROM chat_threads WHERE id = ?", (tid,)
        ).fetchone()["updated_at"]

    time.sleep(1)
    db.add_chat_message(tid, "user", "hello")

    with db.connect() as conn:
        after = conn.execute(
            "SELECT updated_at FROM chat_threads WHERE id = ?", (tid,)
        ).fetchone()["updated_at"]

    assert after > before
