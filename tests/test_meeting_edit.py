"""Integration tests for `cmd_meeting_edit` — the field-picker edit menu."""
import pytest

from snuscoach import cli, db


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


class _Args:
    def __init__(self, id):
        self.id = id


def test_edit_unknown_id_exits(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_meeting_edit(_Args(id=9999))


def test_edit_invalid_choice_exits(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    _stub_inputs(monkeypatch, ["99"])
    with pytest.raises(SystemExit):
        cli.cmd_meeting_edit(_Args(id=mid))


def test_edit_title(monkeypatch, temp_db):
    mid = db.add_meeting("Old", "2026-05-05")
    _stub_inputs(monkeypatch, ["1", "New"])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["title"] == "New"


def test_edit_title_empty_keeps_old(monkeypatch, temp_db):
    mid = db.add_meeting("Old", "2026-05-05")
    _stub_inputs(monkeypatch, ["1", ""])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["title"] == "Old"


def test_edit_attendees(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", attendees="A")
    _stub_inputs(monkeypatch, ["2", "A, B"])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["attendees"] == "A, B"


def test_edit_attendees_clear(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", attendees="A")
    _stub_inputs(monkeypatch, ["2", ""])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["attendees"] is None


def test_edit_date(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    _stub_inputs(monkeypatch, ["3", "2026-05-12"])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["date"] == "2026-05-12"


def test_edit_date_invalid_exits(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    _stub_inputs(monkeypatch, ["3", "garbage"])
    with pytest.raises(SystemExit):
        cli.cmd_meeting_edit(_Args(id=mid))


def test_edit_series_reassign(monkeypatch, temp_db):
    s1 = db.add_meeting_series("S1", None)
    s2 = db.add_meeting_series("S2", None)
    mid = db.add_meeting("X", "2026-05-05", series_id=s1)
    # _pick_or_create_series shows: [1] S1, [2] S2 ; default 0 (no series)
    _stub_inputs(monkeypatch, ["4", "2"])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["series_id"] == s2


def test_edit_series_detach(monkeypatch, temp_db):
    s1 = db.add_meeting_series("S1", None)
    mid = db.add_meeting("X", "2026-05-05", series_id=s1)
    _stub_inputs(monkeypatch, ["4", "0"])
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["series_id"] is None


def test_edit_prep_context(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", prep_context="old")
    _stub_inputs(monkeypatch, ["5"])
    seeds: list[str] = []

    def _multi(_label, initial=""):
        seeds.append(initial)
        return "new context"

    monkeypatch.setattr(cli, "_input_multiline", _multi)
    cli.cmd_meeting_edit(_Args(id=mid))
    assert seeds == ["old"]
    assert db.get_meeting(mid)["prep_context"] == "new context"


def test_edit_prep_brief(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", prep_brief="old brief")
    _stub_inputs(monkeypatch, ["6"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "new brief")
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["prep_brief"] == "new brief"


def test_edit_debrief_notes(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", debrief_notes="old")
    _stub_inputs(monkeypatch, ["7"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "new notes")
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["debrief_notes"] == "new notes"


def test_edit_debrief_summary(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05", debrief_summary="old")
    _stub_inputs(monkeypatch, ["8"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "new summary")
    cli.cmd_meeting_edit(_Args(id=mid))
    assert db.get_meeting(mid)["debrief_summary"] == "new summary"
