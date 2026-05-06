"""Integration tests for all five stakeholder CLI commands.

Real SQLite (temp_db fixture), no LLM calls. Stubs input() via monkeypatch.
"""
import pytest
from datetime import date

from snuscoach import cli, db


class _Args:
    def __init__(self, name=None):
        self.name = name


def _stub_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# ---- stakeholder add ----


def test_add_saves_row(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["Sarah Chen", "VP Eng", "skip", "terse", "clear ownership"])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "New Q1.")
    cli.cmd_stakeholder_add(_Args())
    s = db.get_stakeholder("Sarah Chen")
    assert s["role"] == "VP Eng"
    assert s["relationship"] == "skip"
    assert s["communication_style"] == "terse"
    assert s["what_they_reward"] == "clear ownership"
    assert s["notes"] == "New Q1."


def test_add_optional_fields_empty(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, ["Blake", "", "", "", ""])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")
    cli.cmd_stakeholder_add(_Args())
    s = db.get_stakeholder("Blake")
    assert s["role"] is None
    assert s["relationship"] is None
    assert s["notes"] is None


def test_add_name_from_args(monkeypatch, temp_db):
    prompted = []
    monkeypatch.setattr("builtins.input", lambda p="": prompted.append(p) or "")
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")
    cli.cmd_stakeholder_add(_Args(name="Blake"))
    assert not any("Name" in p for p in prompted)
    assert db.get_stakeholder("Blake") is not None


def test_add_duplicate_name_exits(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice"})
    _stub_inputs(monkeypatch, ["Alice", "", "", "", ""])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_add(_Args())


# ---- stakeholder list ----


def test_list_empty_message(temp_db, capsys):
    cli.cmd_stakeholder_list(None)
    assert "No stakeholders yet" in capsys.readouterr().out


def test_list_shows_all_entries(temp_db, capsys):
    db.add_stakeholder({"name": "Alice", "relationship": "manager"})
    db.add_stakeholder({"name": "Bob", "relationship": "peer"})
    cli.cmd_stakeholder_list(None)
    out = capsys.readouterr().out
    assert "Alice" in out
    assert "Bob" in out


# ---- stakeholder show ----


def test_show_full_profile(temp_db, capsys):
    db.add_stakeholder({
        "name": "Alice",
        "role": "EM",
        "relationship": "manager",
        "communication_style": "direct",
        "what_they_reward": "ownership",
        "notes": "Monthly skip.",
    })
    cli.cmd_stakeholder_show(_Args(name="Alice"))
    out = capsys.readouterr().out
    assert "Alice" in out
    assert "EM" in out
    assert "manager" in out
    assert "direct" in out
    assert "ownership" in out
    assert "Monthly skip." in out


def test_show_missing_exits(temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_show(_Args(name="Ghost"))


def test_show_none_fields_omitted(temp_db, capsys):
    db.add_stakeholder({"name": "Alice"})
    cli.cmd_stakeholder_show(_Args(name="Alice"))
    out = capsys.readouterr().out
    assert "None" not in out


# ---- stakeholder edit ----


def test_edit_missing_stakeholder_exits(monkeypatch, temp_db):
    _stub_inputs(monkeypatch, [])
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_edit(_Args(name="Ghost"))


def test_edit_invalid_choice_exits(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "role": "EM"})
    _stub_inputs(monkeypatch, ["99"])
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_edit(_Args(name="Alice"))


def test_edit_role(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "role": "EM"})
    _stub_inputs(monkeypatch, ["1", "VP Eng"])
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["role"] == "VP Eng"


def test_edit_relationship(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "relationship": "peer"})
    _stub_inputs(monkeypatch, ["2", "skip"])
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["relationship"] == "skip"


def test_edit_communication_style(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice"})
    _stub_inputs(monkeypatch, ["3", "async-first"])
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["communication_style"] == "async-first"


def test_edit_what_they_reward(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice"})
    _stub_inputs(monkeypatch, ["4", "metrics"])
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["what_they_reward"] == "metrics"


def test_edit_notes_seeds_initial(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "notes": "existing note"})
    _stub_inputs(monkeypatch, ["5"])
    captured_initial = []

    def _multi(label, initial=""):
        captured_initial.append(initial)
        return "updated note"

    monkeypatch.setattr(cli, "_input_multiline", _multi)
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert captured_initial == ["existing note"]
    assert db.get_stakeholder("Alice")["notes"] == "updated note"


def test_edit_empty_input_sets_none(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "role": "EM"})
    _stub_inputs(monkeypatch, ["1", ""])
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["role"] is None


# ---- stakeholder note ----


def test_note_prepends_dated_entry(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice"})
    _stub_inputs(monkeypatch, ["Seemed distracted today."])
    cli.cmd_stakeholder_note(_Args(name="Alice"))
    notes = db.get_stakeholder("Alice")["notes"]
    today = date.today().isoformat()
    assert notes.startswith(f"[{today}]")
    assert "Seemed distracted today." in notes


def test_note_prepends_to_existing(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "notes": "old note"})
    _stub_inputs(monkeypatch, ["new observation"])
    cli.cmd_stakeholder_note(_Args(name="Alice"))
    notes = db.get_stakeholder("Alice")["notes"]
    new_idx = notes.index("new observation")
    old_idx = notes.index("old note")
    assert new_idx < old_idx


def test_note_empty_observation_exits(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice"})
    _stub_inputs(monkeypatch, [""])
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_note(_Args(name="Alice"))


def test_note_missing_stakeholder_exits(monkeypatch, temp_db):
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_note(_Args(name="Ghost"))


def test_note_confirms_output(monkeypatch, temp_db, capsys):
    db.add_stakeholder({"name": "Alice"})
    _stub_inputs(monkeypatch, ["Good 1:1 today."])
    cli.cmd_stakeholder_note(_Args(name="Alice"))
    assert "Note added to Alice" in capsys.readouterr().out


# ---- tier validation ----


def test_add_rejects_invalid_tier_then_accepts_valid(monkeypatch, temp_db):
    # "garbage" is rejected; "skip" is accepted; remaining prompts are empty
    _stub_inputs(monkeypatch, ["Alice", "", "garbage", "skip", "", "", ""])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")
    cli.cmd_stakeholder_add(_Args())
    assert db.get_stakeholder("Alice")["relationship"] == "skip"


@pytest.mark.parametrize("tier", ["manager", "skip", "peer", "cross-functional", "influencer", "direct-report", "other"])
def test_add_accepts_all_valid_tiers(monkeypatch, temp_db, tier):
    _stub_inputs(monkeypatch, [tier + "_person", "", tier, "", "", ""])
    monkeypatch.setattr(cli, "_input_multiline", lambda *a, **kw: "")
    cli.cmd_stakeholder_add(_Args())
    name = tier + "_person"
    assert db.get_stakeholder(name)["relationship"] == tier


def test_edit_relationship_invalid_tier_exits(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "relationship": "peer"})
    _stub_inputs(monkeypatch, ["2", "bogus"])
    with pytest.raises(SystemExit):
        cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["relationship"] == "peer"


def test_edit_relationship_empty_clears_to_none(monkeypatch, temp_db):
    db.add_stakeholder({"name": "Alice", "relationship": "peer"})
    _stub_inputs(monkeypatch, ["2", ""])
    cli.cmd_stakeholder_edit(_Args(name="Alice"))
    assert db.get_stakeholder("Alice")["relationship"] is None


def test_list_groups_by_tier(monkeypatch, temp_db, capsys):
    db.add_stakeholder({"name": "Alice", "relationship": "manager"})
    db.add_stakeholder({"name": "Bob", "relationship": "peer"})
    cli.cmd_stakeholder_list(None)
    out = capsys.readouterr().out
    assert "manager:" in out
    assert "peer:" in out
    assert out.index("manager:") < out.index("peer:")
    assert "Alice" in out
    assert "Bob" in out


def test_list_unclassified_shows_raw_rel(monkeypatch, temp_db, capsys):
    db.add_stakeholder({"name": "Alice", "relationship": "director"})
    cli.cmd_stakeholder_list(None)
    out = capsys.readouterr().out
    assert "unclassified:" in out
    assert "director" in out
