"""Integration tests for `cmd_series_*` and the series-creation flow embedded
in `_create_meeting_interactive`.
"""
import pytest

from snuscoach import cli, db


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


class _Args:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_series_add_creates_row(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["1:1 with Sarah", "Weekly with my manager"])
    cli.cmd_series_add(_Args())
    rows = db.list_meeting_series()
    assert len(rows) == 1
    assert rows[0]["name"] == "1:1 with Sarah"
    assert rows[0]["description"] == "Weekly with my manager"


def test_series_add_optional_description(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["Staff", ""])
    cli.cmd_series_add(_Args())
    rows = db.list_meeting_series()
    assert rows[0]["description"] is None


def test_series_add_rejects_empty_name(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, [""])
    with pytest.raises(SystemExit):
        cli.cmd_series_add(_Args())


def test_series_add_rejects_duplicate(monkeypatch, temp_db):
    db.add_meeting_series("Staff", None)
    _stub_inputs(monkeypatch, ["Staff", ""])
    with pytest.raises(SystemExit):
        cli.cmd_series_add(_Args())


def test_series_show_displays_meetings_in_series(monkeypatch, temp_db, capsys):
    sid = db.add_meeting_series("1:1 with Sarah", None)
    db.add_meeting("1:1 with Sarah", "2026-04-15", series_id=sid)
    db.add_meeting("1:1 with Sarah", "2026-04-22", series_id=sid)
    db.add_meeting("Other", "2026-04-20")  # no series

    cli.cmd_series_show(_Args(id=sid))
    out = capsys.readouterr().out
    assert "1:1 with Sarah" in out
    assert "2026-04-15" in out
    assert "2026-04-22" in out
    assert "Meetings (2)" in out
    assert "Other" not in out


def test_series_show_unknown_id_exits(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_series_show(_Args(id=9999))


def test_series_edit_name(monkeypatch, temp_db):
    sid = db.add_meeting_series("Old", None)
    _stub_inputs(monkeypatch, ["1", "New name"])
    cli.cmd_series_edit(_Args(id=sid))
    assert db.get_meeting_series(sid)["name"] == "New name"


def test_series_edit_description(monkeypatch, temp_db):
    sid = db.add_meeting_series("Staff", None)
    _stub_inputs(monkeypatch, ["2", "now with desc"])
    cli.cmd_series_edit(_Args(id=sid))
    assert db.get_meeting_series(sid)["description"] == "now with desc"


def test_series_edit_unknown_id_exits(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_series_edit(_Args(id=9999))


def test_meeting_create_picks_existing_series(monkeypatch, temp_db):
    """When series exist and the user picks one, the meeting links to it."""
    sid = db.add_meeting_series("1:1 with Sarah", None)
    _stub_inputs(
        monkeypatch,
        [
            "1:1 with Sarah",  # title
            "2026-05-05",  # date
            "Sarah",  # attendees
            "",  # series picker — empty accepts default (suggested = matching name = "1")
        ],
    )
    cli.cmd_meeting_create(_Args())

    rows = db.list_meetings()
    assert len(rows) == 1
    assert rows[0]["series_id"] == sid


def test_meeting_create_explicit_no_series(monkeypatch, temp_db):
    db.add_meeting_series("Existing", None)
    _stub_inputs(
        monkeypatch,
        [
            "Coffee with Bobby",
            "2026-05-03",
            "Bobby",
            "0",  # no series
        ],
    )
    cli.cmd_meeting_create(_Args())
    assert db.list_meetings()[0]["series_id"] is None


def test_meeting_create_new_series_inline(monkeypatch, temp_db):
    """Creating a meeting with no existing series → user opts in to create one."""
    _stub_inputs(
        monkeypatch,
        [
            "Quarterly skip with Frekus",  # title
            "2026-05-15",  # date
            "",  # attendees (none)
            "y",  # create series prompt
            "",  # series name (defaults to title)
            "Quarterly skip-level",  # description
        ],
    )
    cli.cmd_meeting_create(_Args())

    series = db.list_meeting_series()
    assert len(series) == 1
    assert series[0]["name"] == "Quarterly skip with Frekus"
    assert series[0]["description"] == "Quarterly skip-level"

    rows = db.list_meetings()
    assert rows[0]["series_id"] == series[0]["id"]


def test_meeting_create_decline_series_with_no_existing(monkeypatch, temp_db):
    """When no series exist and user declines to create one, meeting has no series."""
    _stub_inputs(
        monkeypatch,
        [
            "One-off chat",
            "2026-05-01",
            "",
            "n",  # don't create series
        ],
    )
    cli.cmd_meeting_create(_Args())
    assert db.list_meetings()[0]["series_id"] is None
    assert db.list_meeting_series() == []
