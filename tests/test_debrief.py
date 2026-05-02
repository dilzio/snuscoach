"""Integration tests for `cmd_meeting_debrief` (post-meeting flow).

Mirrors test_prep.py: covers the picker, the run, edit/redo/cancel branches
when a debrief already exists, and persistence to the meetings table.
"""
import pytest

from snuscoach import cli, db


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


class _Args:
    def __init__(self, id=None):
        self.id = id


# ---- explicit-id path ----


def test_debrief_runs_coach_when_no_existing(monkeypatch, temp_db):
    mid = db.add_meeting("1:1 with Sarah", "2026-05-05", attendees="Sarah")

    _stub_inputs(monkeypatch, ["", "y"])  # follow-up empty, save yes
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "raw notes")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "Summary content.")

    cli.cmd_meeting_debrief(_Args(id=mid))

    m = db.get_meeting(mid)
    assert m["debrief_notes"] == "raw notes"
    assert m["debrief_summary"] == "Summary content."


def test_debrief_saves_last_iterated_summary(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    _stub_inputs(monkeypatch, ["push back", "tighten", "", "y"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "notes")

    replies = iter(["FIRST", "SECOND", "THIRD"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(replies))

    cli.cmd_meeting_debrief(_Args(id=mid))
    assert db.get_meeting(mid)["debrief_summary"] == "THIRD"


def test_debrief_skips_save_when_user_declines(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    _stub_inputs(monkeypatch, ["", "n"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "notes")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "summary")

    cli.cmd_meeting_debrief(_Args(id=mid))
    assert db.get_meeting(mid)["debrief_summary"] is None


def test_debrief_rejects_empty_notes(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")

    with pytest.raises(SystemExit):
        cli.cmd_meeting_debrief(_Args(id=mid))


# ---- existing-debrief branches ----


def test_debrief_edit_branch_opens_editor_seeded(monkeypatch, temp_db):
    mid = db.add_meeting(
        "X", "2026-05-05", debrief_notes="n", debrief_summary="OLD summary"
    )
    _stub_inputs(monkeypatch, ["e"])

    seeds: list[str] = []

    def _multi(_label, initial=""):
        seeds.append(initial)
        return "EDITED summary"

    monkeypatch.setattr(cli, "_input_multiline", _multi)

    coach_calls = []
    monkeypatch.setattr(
        cli.coach, "conversation", lambda _msgs: coach_calls.append(1) or "x"
    )

    cli.cmd_meeting_debrief(_Args(id=mid))

    assert seeds == ["OLD summary"]
    assert coach_calls == []
    assert db.get_meeting(mid)["debrief_summary"] == "EDITED summary"


def test_debrief_redo_branch_reruns_coach(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", debrief_notes="n", debrief_summary="OLD")
    _stub_inputs(monkeypatch, ["r", "", "y"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "fresh notes")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "NEW")

    cli.cmd_meeting_debrief(_Args(id=mid))
    m = db.get_meeting(mid)
    assert m["debrief_summary"] == "NEW"
    assert m["debrief_notes"] == "fresh notes"


def test_debrief_cancel_branch_writes_nothing(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", debrief_summary="OLD")
    _stub_inputs(monkeypatch, ["c"])

    cli.cmd_meeting_debrief(_Args(id=mid))
    assert db.get_meeting(mid)["debrief_summary"] == "OLD"


# ---- picker path ----


def test_debrief_no_id_picker_picks_existing(monkeypatch, temp_db):
    target_id = db.add_meeting("Target", "2026-05-05")

    _stub_inputs(monkeypatch, ["1", "", "y"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "n")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "summary")

    cli.cmd_meeting_debrief(_Args(id=None))
    assert db.get_meeting(target_id)["debrief_summary"] == "summary"


# ---- guards ----


def test_debrief_with_unknown_id_exits(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_meeting_debrief(_Args(id=9999))
