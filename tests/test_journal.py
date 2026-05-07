"""Integration tests for cmd_journal, cmd_journals, and journal context block."""
import pytest

from snuscoach import cli, db, prompts


class _Args:
    pass


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# ---- cmd_journal: happy path ----


def test_journal_saves_entry(monkeypatch, temp_db):
    # Opening prompt generates questions; user answers two turns, then saves
    opening_calls = []

    def _fake_draft(msgs):
        opening_calls.append(msgs)
        return "What came out of your 1:1 this week?"

    monkeypatch.setattr(cli.coach, "draft", _fake_draft)
    _stub_inputs(monkeypatch, ["Lots of signals from Alice.", "", "y"])

    cli.cmd_journal(_Args())

    rows = db.list_journal_entries()
    assert len(rows) == 1
    assert rows[0]["entry_type"] == "journal"
    assert "Lots of signals from Alice." in rows[0]["content"]
    assert rows[0]["coach_prompt"] == "What came out of your 1:1 this week?"


def test_journal_multi_turn_joins_user_responses(monkeypatch, temp_db):
    turn = iter(["Q1", "Q2", "Q3"])
    monkeypatch.setattr(cli.coach, "draft", lambda _: next(turn))
    _stub_inputs(monkeypatch, ["First response.", "Second response.", "", "y"])

    cli.cmd_journal(_Args())

    entry = db.get_latest_journal_entry()
    assert "First response." in entry["content"]
    assert "Second response." in entry["content"]


def test_journal_skips_save_when_declined(monkeypatch, temp_db):
    monkeypatch.setattr(cli.coach, "draft", lambda _: "Opening question.")
    _stub_inputs(monkeypatch, ["Some response.", "", "n"])

    cli.cmd_journal(_Args())

    assert db.get_latest_journal_entry() is None


def test_journal_nothing_to_save_if_no_user_turns(monkeypatch, temp_db, capsys):
    monkeypatch.setattr(cli.coach, "draft", lambda _: "Opening question.")
    _stub_inputs(monkeypatch, [""])  # user immediately exits without responding

    cli.cmd_journal(_Args())

    assert db.get_latest_journal_entry() is None
    out = capsys.readouterr().out
    assert "Nothing to save" in out


# ---- cmd_journals: list ----


def test_journals_list_empty(temp_db, capsys):
    cli.cmd_journals(_Args())
    out = capsys.readouterr().out
    assert "No journal entries yet" in out


def test_journals_list_shows_entries(temp_db, capsys):
    db.add_journal_entry("Won the migration project.", entry_type="journal")
    db.add_journal_entry("Alice flagged delays.", entry_type="nudge")

    cli.cmd_journals(_Args())

    out = capsys.readouterr().out
    assert "Won the migration project." in out
    assert "journal" in out
    assert "nudge" in out


def test_journals_list_truncates_long_snippets(temp_db, capsys):
    long_content = "x" * 200
    db.add_journal_entry(long_content, entry_type="journal")

    cli.cmd_journals(_Args())

    out = capsys.readouterr().out
    assert "…" in out


# ---- db: get_latest_journal_entry ----


def test_get_latest_journal_entry_returns_none_when_empty(temp_db):
    assert db.get_latest_journal_entry() is None


def test_get_latest_journal_entry_returns_most_recent(temp_db):
    db.add_journal_entry("First entry.")
    db.add_journal_entry("Second entry.")
    latest = db.get_latest_journal_entry()
    assert latest["content"] == "Second entry."


# ---- prompts: journal entries in context_block ----


def test_context_block_includes_journal_entries(temp_db):
    entries = [{"content": "Alice was terse.", "entry_type": "journal", "created_at": "2026-05-07T09:00:00"}]
    out = prompts.context_block([], [], [], [], [], journal_entries=entries)
    assert "JOURNAL" in out
    assert "Alice was terse." in out


def test_context_block_journal_entry_includes_type_label(temp_db):
    entries = [{"content": "Gap flagged.", "entry_type": "nudge", "created_at": "2026-05-07T09:00:00"}]
    out = prompts.context_block([], [], [], [], [], journal_entries=entries)
    assert "nudge" in out


def test_context_block_journal_truncates_long_entries(temp_db):
    long_content = "z" * 500
    entries = [{"content": long_content, "entry_type": "journal", "created_at": "2026-05-07T09:00:00"}]
    out = prompts.context_block([], [], [], [], [], journal_entries=entries)
    assert "…" in out


def test_context_block_journal_none_is_empty(temp_db):
    out = prompts.context_block([], [], [], [], [], journal_entries=None)
    assert "JOURNAL" in out
    assert "(none recorded yet)" in out


def test_context_block_journal_empty_list_is_empty(temp_db):
    out = prompts.context_block([], [], [], [], [], journal_entries=[])
    assert "(none recorded yet)" in out


def test_context_block_limits_to_seven_entries():
    entries = [
        {"content": f"Entry {i}", "entry_type": "journal", "created_at": f"2026-05-0{i}T09:00:00"}
        for i in range(1, 10)
    ]
    out = prompts.context_block([], [], [], [], [], journal_entries=entries)
    # Only first 7 should appear (most recent in list = earliest indices here)
    assert "Entry 1" in out
    assert "Entry 7" in out
    assert "Entry 8" not in out
    assert "Entry 9" not in out
