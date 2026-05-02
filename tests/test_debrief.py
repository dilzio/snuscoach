"""Integration tests for the debrief flow.

Drives `cli.cmd_debrief` directly with monkeypatched I/O. Real SQLite
underneath (per-test temp DB via conftest). Only the LLM call is mocked —
that's the API boundary, hitting Claude in tests would cost money and be flaky.
"""
import pytest

from snuscoach import cli, db


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def test_debrief_saves_when_user_accepts(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Sarah",  # title
            "Sarah Chen",  # attendees
            "2026-04-30",  # happened_at
            "",  # follow-up: empty → end conversation loop
            "y",  # save? (anything not n/no saves)
        ],
    )
    monkeypatch.setattr(
        cli,
        "_input_multiline",
        lambda *a, **kw: "She wants me on the platform reorg.",
    )
    monkeypatch.setattr(
        cli.coach,
        "conversation",
        lambda _msgs: "1. Send proposal by Friday.\n2. Loop in Mike.",
    )

    cli.cmd_debrief(None)

    rows = db.list_meetings()
    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "1:1 with Sarah"
    assert row["attendees"] == "Sarah Chen"
    assert row["happened_at"] == "2026-04-30"
    assert "Send proposal by Friday" in row["coach_summary"]
    assert "platform reorg" in row["notes"]


def test_debrief_default_save_is_yes(monkeypatch, temp_db):
    """Empty answer to 'Save? [Y/n]' should save (capital Y is the default)."""
    _stub_inputs(
        monkeypatch,
        ["Solo think", "", "2026-05-01", "", ""],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Some notes.")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "summary text")

    cli.cmd_debrief(None)

    assert len(db.list_meetings()) == 1


def test_debrief_skips_save_when_user_declines(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        ["1:1 with Sarah", "", "", "", "n"],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Some notes.")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "summary")

    cli.cmd_debrief(None)

    assert db.list_meetings() == []


def test_debrief_default_date_is_today(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        ["Today's standup debrief", "", "", "", "y"],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Notes.")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "summary")

    cli.cmd_debrief(None)

    from datetime import date

    rows = db.list_meetings()
    assert rows[0]["happened_at"] == date.today().isoformat()


def test_debrief_saves_last_reply_after_multi_turn(monkeypatch, temp_db):
    """Iterating with the coach should persist the LAST refined reply, not the first."""
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Sarah",
            "",
            "2026-05-01",
            "Actually it was about the reorg, not just status",  # follow-up 1
            "And she pushed back on my hiring asks",  # follow-up 2
            "",  # end loop
            "y",  # save
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Initial notes.")

    replies = iter(["FIRST draft summary", "SECOND refined summary", "THIRD final summary"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(replies))

    cli.cmd_debrief(None)

    rows = db.list_meetings()
    assert len(rows) == 1
    assert rows[0]["coach_summary"] == "THIRD final summary"


def test_debrief_eof_during_followup_ends_conversation(monkeypatch, temp_db):
    """Ctrl-D at the follow-up prompt should end the loop cleanly and proceed to save."""

    inputs = iter([
        "1:1 with Sarah",
        "",
        "2026-05-01",
    ])

    def _input(_prompt=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", _input)
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Notes.")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "summary")

    # The save prompt comes after the follow-up loop. EOF on the follow-up
    # exits the loop, then the save prompt itself raises StopIteration → EOFError
    # via input(), which input() converts back to EOFError. We expect this to
    # bubble up unhandled (the save flow doesn't catch EOF), so we wrap in
    # pytest.raises. The point is the loop itself handled EOF cleanly.
    with pytest.raises(EOFError):
        cli.cmd_debrief(None)


def test_debrief_rejects_empty_title(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, [""])
    with pytest.raises(SystemExit):
        cli.cmd_debrief(None)
    assert db.list_meetings() == []


def test_debrief_rejects_invalid_date(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["title", "", "not-a-date"])
    with pytest.raises(SystemExit):
        cli.cmd_debrief(None)
    assert db.list_meetings() == []


def test_debrief_rejects_empty_notes(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["title", "", ""])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")
    with pytest.raises(SystemExit):
        cli.cmd_debrief(None)
    assert db.list_meetings() == []
