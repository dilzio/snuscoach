"""Integration tests for cmd_nudge, _compute_nudge_gaps, and nudge prompt functions."""
import pytest
from datetime import date, timedelta

from snuscoach import cli, db, prompts


class _Args:
    pass


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def _today():
    return date.today().isoformat()


def _days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


# ---- _compute_nudge_gaps: gap detection ----


def test_gaps_empty_db(temp_db):
    gaps = cli._compute_nudge_gaps()
    assert gaps["undebriefed_meetings"] == []
    assert gaps["wins_without_post"] == 0
    assert gaps["silent_stakeholders"] == []
    assert gaps["journal_gap_days"] == 999  # never journaled


def test_gaps_detects_undebriefed_meeting(temp_db):
    db.add_meeting("1:1 Alice", _days_ago(2))  # no debrief_summary
    gaps = cli._compute_nudge_gaps()
    assert len(gaps["undebriefed_meetings"]) == 1
    assert gaps["undebriefed_meetings"][0]["title"] == "1:1 Alice"


def test_gaps_ignores_debriefed_meeting(temp_db):
    mid = db.add_meeting("1:1 Alice", _days_ago(2))
    db.update_meeting(mid, debrief_summary="All good.")
    gaps = cli._compute_nudge_gaps()
    assert gaps["undebriefed_meetings"] == []


def test_gaps_ignores_old_meetings(temp_db):
    db.add_meeting("Old meeting", _days_ago(10))  # outside 7-day window
    gaps = cli._compute_nudge_gaps()
    assert gaps["undebriefed_meetings"] == []


def test_gaps_detects_wins_without_post(temp_db):
    db.add_win("Shipped the migration", "Big deal.")
    gaps = cli._compute_nudge_gaps()
    assert gaps["wins_without_post"] == 1


def test_gaps_no_win_gap_when_post_exists(temp_db):
    db.add_win("Shipped the migration", "Big deal.")
    db.add_post("We shipped.", "Slack #eng", "team-broadcast", _today())
    gaps = cli._compute_nudge_gaps()
    assert gaps["wins_without_post"] == 0


def test_gaps_detects_silent_stakeholder(temp_db):
    # Add a stakeholder created 31+ days ago with no recent dated note
    import sqlite3
    old_date = _days_ago(40)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO stakeholders (name, role, relationship, communication_style, "
            "what_they_reward, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Alice", "EM", "manager", None, None, "General notes, no date.", old_date, old_date),
        )

    gaps = cli._compute_nudge_gaps()
    assert any(s["name"] == "Alice" for s in gaps["silent_stakeholders"])


def test_gaps_ignores_recently_added_stakeholder(temp_db):
    db.add_stakeholder({"name": "Bob", "role": "PM"})  # created_at = now
    gaps = cli._compute_nudge_gaps()
    assert not any(s["name"] == "Bob" for s in gaps["silent_stakeholders"])


def test_gaps_ignores_stakeholder_with_recent_note(temp_db):
    import sqlite3
    old_date = _days_ago(40)
    recent_note = f"[{_days_ago(5)}] Had a good chat."
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO stakeholders (name, role, relationship, communication_style, "
            "what_they_reward, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Carol", "Director", "skip", None, None, recent_note, old_date, old_date),
        )

    gaps = cli._compute_nudge_gaps()
    assert not any(s["name"] == "Carol" for s in gaps["silent_stakeholders"])


def test_gaps_journal_gap_days(temp_db):
    db.add_journal_entry("Yesterday's entry.")
    # Manually set created_at to 3 days ago
    with db.connect() as conn:
        conn.execute(
            "UPDATE journal_entries SET created_at = ?, updated_at = ?",
            (_days_ago(3) + "T09:00:00", _days_ago(3) + "T09:00:00"),
        )
    gaps = cli._compute_nudge_gaps()
    assert gaps["journal_gap_days"] == 3


# ---- cmd_nudge: interactive mode ----


def test_nudge_interactive_saves_entry(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "interactive")
    turn = iter(["What came out of your 1:1?", "Interesting — tell me more."])
    monkeypatch.setattr(cli.coach, "conversation", lambda _: next(turn))
    _stub_inputs(monkeypatch, ["Alice seemed worried.", "", "y"])

    cli.cmd_nudge(_Args())

    entry = db.get_latest_journal_entry()
    assert entry is not None
    assert entry["entry_type"] == "nudge"
    # Both parties labelled in transcript
    assert "coach: What came out of your 1:1?" in entry["content"]
    assert "you: Alice seemed worried." in entry["content"]
    # Internal task prompt excluded
    assert "TASK:" not in entry["content"]


def test_nudge_interactive_skips_save_when_declined(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "interactive")
    monkeypatch.setattr(cli.coach, "conversation", lambda _: "Question.")
    _stub_inputs(monkeypatch, ["Some response.", "", "n"])

    cli.cmd_nudge(_Args())

    assert db.get_latest_journal_entry() is None


def test_nudge_interactive_uses_opus(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "interactive")
    opus_calls = []
    sonnet_calls = []
    monkeypatch.setattr(cli.coach, "conversation", lambda msgs: opus_calls.append(msgs) or "Q.")
    monkeypatch.setattr(cli.coach, "draft", lambda msgs: sonnet_calls.append(msgs) or "Q.")
    _stub_inputs(monkeypatch, ["", "n"])

    cli.cmd_nudge(_Args())

    assert len(opus_calls) >= 1
    assert len(sonnet_calls) == 0


# ---- cmd_nudge: report mode ----


def test_nudge_report_prints_gaps_and_actions(monkeypatch, temp_db, capsys):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "report")
    db.add_meeting("1:1 Alice", _days_ago(2))  # undebriefed
    monkeypatch.setattr(cli.coach, "draft", lambda _: "1. 1:1 Alice missing debrief — risk: signals lost.")
    _stub_inputs(monkeypatch, [""])  # skip item selection

    cli.cmd_nudge(_Args())

    out = capsys.readouterr().out
    assert "Actions" in out
    assert "make debrief" in out


def test_nudge_report_saves_nudge_entry(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "report")
    db.add_meeting("Staff meeting", _days_ago(1))
    monkeypatch.setattr(cli.coach, "draft", lambda _: "Report.")
    _stub_inputs(monkeypatch, [""])

    cli.cmd_nudge(_Args())

    entry = db.get_latest_journal_entry()
    assert entry is not None
    assert entry["entry_type"] == "nudge"


def test_nudge_report_no_gaps_prints_on_track(monkeypatch, temp_db, capsys):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "report")
    monkeypatch.setattr(cli.coach, "draft", lambda _: "")
    # Empty DB + no journal entries (but journal_gap_days=999 triggers journal item)
    # Add a journal entry to suppress the journal gap item
    db.add_journal_entry("Today's entry.")

    cli.cmd_nudge(_Args())

    out = capsys.readouterr().out
    assert "No gaps detected" in out


def test_nudge_report_uses_sonnet(monkeypatch, temp_db):
    monkeypatch.setenv("SNUSCOACH_NUDGE_MODE", "report")
    db.add_meeting("Some meeting", _days_ago(1))
    opus_calls = []
    sonnet_calls = []
    monkeypatch.setattr(cli.coach, "conversation", lambda msgs: opus_calls.append(msgs) or "Q.")
    monkeypatch.setattr(cli.coach, "draft", lambda msgs: sonnet_calls.append(msgs) or "Report.")
    _stub_inputs(monkeypatch, [""])

    cli.cmd_nudge(_Args())

    assert len(sonnet_calls) >= 1
    assert len(opus_calls) == 0


def test_nudge_defaults_to_interactive_when_env_unset(monkeypatch, temp_db):
    monkeypatch.delenv("SNUSCOACH_NUDGE_MODE", raising=False)
    opus_calls = []
    monkeypatch.setattr(cli.coach, "conversation", lambda msgs: opus_calls.append(msgs) or "Q.")
    monkeypatch.setattr(cli.coach, "draft", lambda _: "Q.")
    _stub_inputs(monkeypatch, ["", "n"])

    cli.cmd_nudge(_Args())

    assert len(opus_calls) >= 1


# ---- prompts: nudge_analysis_prompt ----


def test_nudge_analysis_prompt_interactive_mentions_gaps():
    gaps = {
        "undebriefed_meetings": [{"title": "1:1 Alice", "date": "2026-05-05"}],
        "wins_without_post": 2,
        "silent_stakeholders": [],
        "journal_gap_days": 0,
    }
    text = prompts.nudge_analysis_prompt(gaps, mode="interactive")
    assert "1:1 Alice" in text
    assert "2 win" in text


def test_nudge_analysis_prompt_report_mode():
    gaps = {
        "undebriefed_meetings": [],
        "wins_without_post": 0,
        "silent_stakeholders": [{"name": "Bob"}],
        "journal_gap_days": 5,
    }
    text = prompts.nudge_analysis_prompt(gaps, mode="report")
    assert "Bob" in text
    assert "5 days" in text
    assert "report" in text.lower()


def test_nudge_analysis_prompt_no_gaps():
    gaps = {
        "undebriefed_meetings": [],
        "wins_without_post": 0,
        "silent_stakeholders": [],
        "journal_gap_days": 0,
    }
    text = prompts.nudge_analysis_prompt(gaps)
    assert "No specific gaps" in text
