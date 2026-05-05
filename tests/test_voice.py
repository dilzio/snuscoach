"""Integration tests for voice profile: DB layer, CLI commands, context rendering."""
import json
import sys
from unittest.mock import patch

import pytest

from snuscoach import db, prompts


# ---- DB layer ----


def test_add_and_retrieve(temp_db):
    sid = db.add_voice_sample("Short and punchy. No fluff.", "Slack #eng")
    s = db.get_voice_sample(sid)
    assert s["content"] == "Short and punchy. No fluff."
    assert s["description"] == "Slack #eng"
    assert s["created_at"]


def test_add_without_description(temp_db):
    sid = db.add_voice_sample("Just the writing.", None)
    s = db.get_voice_sample(sid)
    assert s["description"] is None


def test_list_returns_newest_first(temp_db):
    db.add_voice_sample("first", None)
    db.add_voice_sample("second", None)
    db.add_voice_sample("third", None)
    rows = db.list_voice_samples()
    assert [r["content"] for r in rows] == ["third", "second", "first"]


def test_list_empty(temp_db):
    assert db.list_voice_samples() == []


def test_get_nonexistent(temp_db):
    assert db.get_voice_sample(9999) is None


def test_delete(temp_db):
    sid = db.add_voice_sample("to be deleted", None)
    assert db.delete_voice_sample(sid) is True
    assert db.get_voice_sample(sid) is None


def test_delete_nonexistent(temp_db):
    assert db.delete_voice_sample(9999) is False


def test_schema_idempotent(temp_db):
    db.init_db()
    db.init_db()
    db.add_voice_sample("still works", None)
    assert len(db.list_voice_samples()) == 1


# ---- prompts / context rendering ----


def _make_sample(content, description=None, created_at="2026-05-01T10:00:00"):
    return {"id": 1, "content": content, "description": description, "created_at": created_at}


def test_voice_block_empty():
    block = prompts._render_voice_block([])
    assert "none recorded yet" in block
    assert "snuscoach voice add" in block


def test_voice_block_renders_content():
    sample = _make_sample("Short. Direct. No filler.", "Slack #eng")
    block = prompts._render_voice_block([sample])
    assert "Short. Direct. No filler." in block
    assert "Slack #eng" in block
    assert "2026-05-01" in block


def test_voice_block_caps_at_ten():
    samples = [_make_sample(f"unique-content-{i}") for i in range(15)]
    block = prompts._render_voice_block(samples)
    assert block.count("unique-content-") == 10


def test_context_block_includes_voice_section():
    sample = _make_sample("Terse. No corporate speak.")
    ctx = prompts.context_block([], [], [], [], [], voice_samples=[sample])
    assert "VOICE PROFILE" in ctx
    assert "Terse. No corporate speak." in ctx


def test_context_block_no_voice_samples_arg():
    ctx = prompts.context_block([], [], [], [], [])
    assert "VOICE PROFILE" in ctx
    assert "none recorded yet" in ctx


def test_voice_section_before_meetings():
    sample = _make_sample("my writing style")
    ctx = prompts.context_block([], [], [], [], [], voice_samples=[sample])
    voice_pos = ctx.index("VOICE PROFILE")
    meetings_pos = ctx.index("MEETINGS")
    assert voice_pos < meetings_pos


# ---- CLI: voice add ----


def test_cmd_voice_add_saves_sample(temp_db, monkeypatch, capsys):
    inputs = iter(["Slack #engineering", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    with patch("snuscoach.cli._input_multiline", return_value="Short. Punchy. No waffle."):
        from snuscoach.cli import cmd_voice_add
        cmd_voice_add(None)

    out = capsys.readouterr().out
    assert "Saved voice sample #1" in out
    assert "Slack #engineering" in out
    samples = db.list_voice_samples()
    assert len(samples) == 1
    assert samples[0]["content"] == "Short. Punchy. No waffle."
    assert samples[0]["description"] == "Slack #engineering"


def test_cmd_voice_add_no_description(temp_db, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "")
    with patch("snuscoach.cli._input_multiline", return_value="bare sample"):
        from snuscoach.cli import cmd_voice_add
        cmd_voice_add(None)

    samples = db.list_voice_samples()
    assert samples[0]["description"] is None


def test_cmd_voice_add_empty_content_exits(temp_db, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    with patch("snuscoach.cli._input_multiline", return_value=""):
        from snuscoach.cli import cmd_voice_add
        with pytest.raises(SystemExit):
            cmd_voice_add(None)


# ---- CLI: voice list ----


def test_cmd_voice_list_empty(temp_db, capsys):
    from snuscoach.cli import cmd_voice_list
    cmd_voice_list(None)
    out = capsys.readouterr().out
    assert "No voice samples yet" in out


def test_cmd_voice_list_shows_entries(temp_db, capsys):
    db.add_voice_sample("First sample content here", "Slack")
    db.add_voice_sample("Second sample content here", None)
    from snuscoach.cli import cmd_voice_list
    cmd_voice_list(None)
    out = capsys.readouterr().out
    assert "First sample" in out
    assert "Second sample" in out
    assert "Slack" in out


def test_cmd_voice_list_truncates_long_first_line(temp_db, capsys):
    db.add_voice_sample("A" * 100, None)
    from snuscoach.cli import cmd_voice_list
    cmd_voice_list(None)
    out = capsys.readouterr().out
    assert "…" in out


# ---- CLI: voice show ----


def test_cmd_voice_show(temp_db, capsys):
    sid = db.add_voice_sample("Full content here.", "weekly email")
    from snuscoach.cli import cmd_voice_show

    class Args:
        id = sid

    cmd_voice_show(Args())
    out = capsys.readouterr().out
    assert "Full content here." in out
    assert "weekly email" in out


def test_cmd_voice_show_missing_exits(temp_db):
    from snuscoach.cli import cmd_voice_show

    class Args:
        id = 999

    with pytest.raises(SystemExit):
        cmd_voice_show(Args())


# ---- CLI: voice delete ----


def test_cmd_voice_delete_confirmed(temp_db, monkeypatch, capsys):
    sid = db.add_voice_sample("to delete", None)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    from snuscoach.cli import cmd_voice_delete

    class Args:
        id = sid

    cmd_voice_delete(Args())
    out = capsys.readouterr().out
    assert "Deleted" in out
    assert db.get_voice_sample(sid) is None


def test_cmd_voice_delete_cancelled(temp_db, monkeypatch, capsys):
    sid = db.add_voice_sample("stays", None)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    from snuscoach.cli import cmd_voice_delete

    class Args:
        id = sid

    cmd_voice_delete(Args())
    out = capsys.readouterr().out
    assert "Cancelled" in out
    assert db.get_voice_sample(sid) is not None


def test_cmd_voice_delete_missing_exits(temp_db):
    from snuscoach.cli import cmd_voice_delete

    class Args:
        id = 999

    with pytest.raises(SystemExit):
        cmd_voice_delete(Args())
