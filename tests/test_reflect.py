"""Integration tests for `cmd_reflect` and related prompt/context changes."""
import pytest

from snuscoach import cli, db, prompts


class _Args:
    def __init__(self, since=None):
        self.since = since


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# ---- cmd_reflect: core flow ----


def test_reflect_runs_coach_and_saves(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["y"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "Pattern brief.")

    cli.cmd_reflect(_Args())

    rows = db.get_reflections()
    assert len(rows) == 1
    assert rows[0]["content"] == "Pattern brief."
    assert rows[0]["since_date"] is None


def test_reflect_with_since_date_saves_window(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["y"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "Windowed brief.")

    cli.cmd_reflect(_Args(since="2026-04-01"))

    r = db.get_latest_reflection()
    assert r["since_date"] == "2026-04-01"


def test_reflect_skips_save_when_declined(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["n"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "Brief.")

    cli.cmd_reflect(_Args())

    assert db.get_latest_reflection() is None


def test_reflect_sends_reflect_prompt_as_user_message(monkeypatch, temp_db):
    captured = []
    _stub_inputs(monkeypatch, ["n"])
    monkeypatch.setattr(
        cli.coach, "conversation",
        lambda msgs: captured.append(msgs) or "Brief."
    )

    cli.cmd_reflect(_Args())

    assert len(captured) == 1
    assert captured[0][0]["role"] == "user"
    assert "TASK: Political Pattern Reflection Brief" in captured[0][0]["content"]


def test_reflect_since_date_appears_in_prompt(monkeypatch, temp_db):
    captured = []
    _stub_inputs(monkeypatch, ["n"])
    monkeypatch.setattr(
        cli.coach, "conversation",
        lambda msgs: captured.append(msgs) or "Brief."
    )

    cli.cmd_reflect(_Args(since="2026-03-01"))

    prompt_text = captured[0][0]["content"]
    assert "2026-03-01" in prompt_text


def test_reflect_rejects_invalid_since_date(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_reflect(_Args(since="not-a-date"))


def test_reflect_multiple_runs_each_saved(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["y", "y"])
    calls = iter(["First brief.", "Second brief."])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(calls))

    cli.cmd_reflect(_Args())
    cli.cmd_reflect(_Args())

    rows = db.get_reflections(limit=10)
    assert len(rows) == 2
    assert rows[0]["content"] == "Second brief."
    assert rows[1]["content"] == "First brief."


# ---- prompts: context_block includes latest reflection ----


def test_context_block_includes_latest_reflection(temp_db):
    db.save_reflection("Flagged: avoids Dana.")
    r = db.get_latest_reflection()
    output = prompts.context_block([], [], [], [], [], latest_reflection=r)
    assert "LATEST REFLECTION" in output
    assert "Flagged: avoids Dana." in output


def test_context_block_omits_reflection_section_when_none(temp_db):
    output = prompts.context_block([], [], [], [], [], latest_reflection=None)
    assert "LATEST REFLECTION" not in output


def test_context_block_reflection_includes_since_date(temp_db):
    db.save_reflection("Windowed brief.", since_date="2026-04-01")
    r = db.get_latest_reflection()
    output = prompts.context_block([], [], [], [], [], latest_reflection=r)
    assert "since 2026-04-01" in output


# ---- prompts: series meeting count in meetings block ----


def test_context_block_series_shows_meeting_count(temp_db):
    sid = db.add_meeting_series("1:1 with Sarah", None)
    db.add_meeting("1:1 #1", "2026-05-01", series_id=sid)
    db.add_meeting("1:1 #2", "2026-05-08", series_id=sid)
    db.add_meeting("1:1 #3", "2026-05-15", series_id=sid)
    meetings = db.list_meetings()
    series = db.list_meeting_series()
    output = prompts.context_block([], [], [], meetings, series)
    assert "1:1 with Sarah" in output
    assert "3 meetings" in output


def test_context_block_series_singular_meeting_count(temp_db):
    sid = db.add_meeting_series("Solo review", None)
    db.add_meeting("Solo review", "2026-05-01", series_id=sid)
    meetings = db.list_meetings()
    series = db.list_meeting_series()
    output = prompts.context_block([], [], [], meetings, series)
    assert "1 meeting" in output
    assert "1 meetings" not in output


# ---- prompts: system prompt includes pattern-surfacing directive ----


def test_system_prompt_includes_pattern_language():
    profile = {"name": "Matt", "role": "Senior SWE"}
    text = prompts.system_prompt(profile)
    assert "Surface patterns proactively" in text
    assert "LATEST REFLECTION" in text
