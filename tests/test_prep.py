"""Integration tests for `cmd_meeting_prep`.

Covers the meeting picker, the prep run, the edit/redo/cancel branches when
a prep already exists, and persistence to the meetings table.

Real SQLite via temp_db fixture; only `coach.conversation` is mocked.
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


def test_prep_runs_coach_when_no_existing_prep(monkeypatch, temp_db):
    mid = db.add_meeting("1:1 with Sarah", "2026-05-05", attendees="Sarah")

    _stub_inputs(monkeypatch, ["", "y"])  # follow-up empty, save yes
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context body")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "Brief content.")

    cli.cmd_meeting_prep(_Args(id=mid))

    m = db.get_meeting(mid)
    assert m["prep_context"] == "context body"
    assert m["prep_brief"] == "Brief content."


def test_prep_reuses_existing_context(monkeypatch, temp_db):
    """If prep_context is already set, cmd_meeting_prep doesn't open the editor."""
    mid = db.add_meeting(
        "1:1 with Sarah",
        "2026-05-05",
        prep_context="reorg context already here",
    )

    _stub_inputs(monkeypatch, ["", "y"])
    multiline_calls: list[str] = []
    monkeypatch.setattr(
        cli, "_input_multiline", lambda label, **kw: multiline_calls.append(label) or ""
    )
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "Brief.")

    cli.cmd_meeting_prep(_Args(id=mid))

    # Editor should NOT have been invoked for prep context (reused from DB)
    assert multiline_calls == []
    m = db.get_meeting(mid)
    assert m["prep_context"] == "reorg context already here"
    assert m["prep_brief"] == "Brief."


def test_prep_saves_last_iterated_brief(monkeypatch, temp_db):
    mid = db.add_meeting("1:1 with Sarah", "2026-05-05")
    _stub_inputs(
        monkeypatch,
        ["push back on this", "tighten section 3", "", "y"],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context")

    replies = iter(["FIRST", "SECOND", "THIRD final"])
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: next(replies))

    cli.cmd_meeting_prep(_Args(id=mid))
    assert db.get_meeting(mid)["prep_brief"] == "THIRD final"


def test_prep_skips_save_when_user_declines(monkeypatch, temp_db):
    mid = db.add_meeting("X", "2026-05-05")
    _stub_inputs(monkeypatch, ["", "n"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "brief")

    cli.cmd_meeting_prep(_Args(id=mid))
    assert db.get_meeting(mid)["prep_brief"] is None


# ---- existing-prep branches: edit / redo / cancel ----


def test_prep_edit_branch_opens_editor_seeded_with_existing(monkeypatch, temp_db):
    mid = db.add_meeting(
        "X", "2026-05-05", prep_context="ctx", prep_brief="OLD brief"
    )
    _stub_inputs(monkeypatch, ["e"])

    seeds: list[str] = []

    def _multi(_label, initial=""):
        seeds.append(initial)
        return "EDITED brief"

    monkeypatch.setattr(cli, "_input_multiline", _multi)

    coach_calls = []
    monkeypatch.setattr(
        cli.coach, "conversation", lambda _msgs: coach_calls.append(1) or "x"
    )

    cli.cmd_meeting_prep(_Args(id=mid))

    assert seeds == ["OLD brief"]
    assert coach_calls == []  # edit branch must NOT call the coach
    assert db.get_meeting(mid)["prep_brief"] == "EDITED brief"


def test_prep_redo_branch_reruns_coach(monkeypatch, temp_db):
    mid = db.add_meeting(
        "X", "2026-05-05", prep_context="ctx", prep_brief="OLD"
    )
    _stub_inputs(monkeypatch, ["r", "", "y"])  # redo, no follow-up, save
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "shouldn't be called")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "NEW brief")

    cli.cmd_meeting_prep(_Args(id=mid))
    assert db.get_meeting(mid)["prep_brief"] == "NEW brief"


def test_prep_cancel_branch_writes_nothing(monkeypatch, temp_db):
    mid = db.add_meeting(
        "X", "2026-05-05", prep_context="ctx", prep_brief="OLD"
    )
    _stub_inputs(monkeypatch, ["c"])

    coach_calls = []
    monkeypatch.setattr(
        cli.coach, "conversation", lambda _msgs: coach_calls.append(1) or "x"
    )

    cli.cmd_meeting_prep(_Args(id=mid))
    assert coach_calls == []
    assert db.get_meeting(mid)["prep_brief"] == "OLD"  # unchanged


def test_prep_default_choice_when_existing_is_redo(monkeypatch, temp_db):
    mid = db.add_meeting(
        "X", "2026-05-05", prep_context="ctx", prep_brief="OLD"
    )
    # Empty answer for the edit/redo/cancel prompt → defaults to redo
    _stub_inputs(monkeypatch, ["", "", "y"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "x")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "NEW")

    cli.cmd_meeting_prep(_Args(id=mid))
    assert db.get_meeting(mid)["prep_brief"] == "NEW"


# ---- no-id picker: pick existing ----


def test_prep_no_id_picker_picks_existing_meeting(monkeypatch, temp_db):
    db.add_meeting("Older", "2026-04-15")
    target_id = db.add_meeting("Target", "2026-05-05")
    db.add_meeting("Newer", "2026-05-10")

    # Picker shows newest first: [1] Newer, [2] Target, [3] Older
    _stub_inputs(monkeypatch, ["2", "", "y"])  # pick Target, no follow-up, save
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "ctx")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "brief")

    cli.cmd_meeting_prep(_Args(id=None))

    m = db.get_meeting(target_id)
    assert m["prep_brief"] == "brief"


def test_prep_no_id_no_meetings_creates_new(monkeypatch, temp_db):
    """First-run flow: no meetings → create new inline."""
    _stub_inputs(
        monkeypatch,
        [
            # _create_meeting_interactive
            "1:1 with Sarah",  # title
            "2026-05-05",  # date
            "Sarah",  # attendees
            # _pick_or_create_series with no series existing
            "",  # default Y to create
            # _create_series_interactive
            "",  # series name (defaults to title)
            "",  # description
            # back in cmd_meeting_prep
            "",  # follow-up empty
            "y",  # save
        ],
    )
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "context")
    monkeypatch.setattr(cli.coach, "conversation", lambda _msgs: "brief")

    cli.cmd_meeting_prep(_Args(id=None))

    rows = db.list_meetings()
    assert len(rows) == 1
    m = rows[0]
    assert m["title"] == "1:1 with Sarah"
    assert m["prep_brief"] == "brief"

    series = db.list_meeting_series()
    assert len(series) == 1
    assert series[0]["name"] == "1:1 with Sarah"
    assert m["series_id"] == series[0]["id"]


# ---- guards ----


def test_prep_with_unknown_id_exits(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_meeting_prep(_Args(id=9999))
