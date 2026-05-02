"""Integration tests for the pre-meeting prep flow.

Covers input handling, the multi-turn follow-up loop (which fixes the
clarifying-questions-with-nowhere-to-answer bug), and persistence to the
prep_briefs table.
"""
import pytest

from snuscoach import cli, db


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def test_prep_runs_one_turn_when_followup_empty(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Frekus",  # title
            "Matt, Frekus",  # attendees
            "2026-05-05",  # prep_for
            "",  # follow-up: empty → end loop after first reply
            "y",  # save? yes
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Architecture buy-in update.")

    calls: list[list[dict]] = []

    def _conv(messages):
        calls.append(list(messages))
        return "Provisional brief — three clarifying questions first."

    monkeypatch.setattr(cli.coach, "conversation", _conv)

    cli.cmd_prep(None)

    # Exactly one model call when the user immediately ends the loop
    assert len(calls) == 1
    # First call has just the seeded user message
    assert len(calls[0]) == 1
    assert calls[0][0]["role"] == "user"
    assert "Pre-meeting prep brief" in calls[0][0]["content"]


def test_prep_iterates_when_user_answers_followup(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Frekus",
            "Matt, Frekus",
            "2026-05-05",
            "Yes — Frekus has seen designs",  # answers a clarifying question
            "And the architecture connects to acquisition integration",
            "",  # end loop
            "y",  # save
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Architecture update.")

    calls: list[int] = []

    def _conv(messages):
        calls.append(len(messages))
        return f"Reply #{len(calls)}"

    monkeypatch.setattr(cli.coach, "conversation", _conv)

    cli.cmd_prep(None)

    # Three model calls: initial + two follow-ups
    assert len(calls) == 3
    # Message history grows by 2 each turn (user + assistant), starting at 1 user
    assert calls == [1, 3, 5]


def test_prep_saves_to_brief_history(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Frekus",
            "Matt, Frekus",
            "2026-05-05",
            "",  # end loop
            "y",  # save
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Architecture update.")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "The brief content.")

    cli.cmd_prep(None)

    rows = db.list_prep_briefs()
    assert len(rows) == 1
    assert rows[0]["title"] == "1:1 with Frekus"
    assert rows[0]["attendees"] == "Matt, Frekus"
    assert rows[0]["prep_for"] == "2026-05-05"
    assert rows[0]["context"] == "Architecture update."
    assert rows[0]["brief"] == "The brief content."


def test_prep_saves_last_iterated_brief(monkeypatch, temp_db):
    """The persisted brief is the LAST coach reply, not the first rough draft."""
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Frekus",
            "",
            "2026-05-05",
            "Push back on this draft",  # follow-up
            "And tighten section 3",  # follow-up
            "",  # end loop
            "y",  # save
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "Context.")

    replies = iter(["FIRST rough", "SECOND refined", "THIRD final"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(replies))

    cli.cmd_prep(None)

    rows = db.list_prep_briefs()
    assert len(rows) == 1
    assert rows[0]["brief"] == "THIRD final"


def test_prep_default_save_is_yes(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        ["title", "", "2026-05-05", "", ""],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "brief")

    cli.cmd_prep(None)

    assert len(db.list_prep_briefs()) == 1


def test_prep_skips_save_when_user_declines(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        ["title", "", "2026-05-05", "", "n"],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "brief")

    cli.cmd_prep(None)

    assert db.list_prep_briefs() == []


def test_prep_default_date_is_today(monkeypatch, temp_db):
    _stub_inputs(
        monkeypatch,
        ["title", "", "", "", "y"],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "brief")

    cli.cmd_prep(None)

    from datetime import date

    rows = db.list_prep_briefs()
    assert rows[0]["prep_for"] == date.today().isoformat()


def test_prep_rejects_empty_title(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, [""])
    with pytest.raises(SystemExit):
        cli.cmd_prep(None)


def test_prep_rejects_invalid_date(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["title", "", "garbage-date"])
    with pytest.raises(SystemExit):
        cli.cmd_prep(None)
    assert db.list_prep_briefs() == []
