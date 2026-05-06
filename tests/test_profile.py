"""Integration tests for user profile: DB layer, prompts, CLI commands, profile check."""
import pytest

from snuscoach import db, prompts


# ---- helpers ----

def _minimal(name="Alice"):
    return {
        "name": name,
        "role": None,
        "org_context": None,
        "political_strengths": None,
        "political_weaknesses": None,
        "coaching_goals": None,
        "communication_style": None,
    }


def _full(name="Bob"):
    return {
        "name": name,
        "role": "Senior SWE",
        "org_context": "300-person Series B, 10-person eng team",
        "political_strengths": "strong cross-team relationships",
        "political_weaknesses": "avoids conflict",
        "coaching_goals": "promoted to Staff in 12 months",
        "communication_style": "direct, written-first",
    }


# ---- DB layer ----

def test_add_and_retrieve(temp_db):
    pid = db.add_user_profile(_full("Carol"))
    p = db.get_user_profile(pid)
    assert p["name"] == "Carol"
    assert p["role"] == "Senior SWE"
    assert p["org_context"] == "300-person Series B, 10-person eng team"
    assert p["political_strengths"] == "strong cross-team relationships"
    assert p["political_weaknesses"] == "avoids conflict"
    assert p["coaching_goals"] == "promoted to Staff in 12 months"
    assert p["communication_style"] == "direct, written-first"
    assert p["created_at"]
    assert p["updated_at"]


def test_add_minimal(temp_db):
    pid = db.add_user_profile(_minimal("Solo"))
    p = db.get_user_profile(pid)
    assert p["name"] == "Solo"
    assert p["role"] is None
    assert p["org_context"] is None


def test_list_empty(temp_db):
    assert db.list_user_profiles() == []


def test_list_ordered_oldest_first(temp_db):
    db.add_user_profile(_minimal("First"))
    db.add_user_profile(_minimal("Second"))
    db.add_user_profile(_minimal("Third"))
    rows = db.list_user_profiles()
    assert [r["name"] for r in rows] == ["First", "Second", "Third"]


def test_get_default_profile_returns_oldest(temp_db):
    db.add_user_profile(_minimal("Oldest"))
    db.add_user_profile(_minimal("Newer"))
    p = db.get_default_profile()
    assert p["name"] == "Oldest"


def test_get_default_profile_none_when_empty(temp_db):
    assert db.get_default_profile() is None


def test_get_by_name_found(temp_db):
    db.add_user_profile(_minimal("Dana"))
    p = db.get_user_profile_by_name("Dana")
    assert p is not None
    assert p["name"] == "Dana"


def test_get_by_name_missing(temp_db):
    assert db.get_user_profile_by_name("Nobody") is None


def test_get_by_name_case_sensitive(temp_db):
    db.add_user_profile(_minimal("Evan"))
    assert db.get_user_profile_by_name("evan") is None


def test_schema_idempotent(temp_db):
    db.init_db()
    db.init_db()
    db.add_user_profile(_minimal("Idempotent"))
    assert len(db.list_user_profiles()) == 1


def test_init_creates_user_profiles_table(temp_db_path):
    import sqlite3
    db.init_db()
    conn = sqlite3.connect(str(temp_db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "user_profiles" in tables


# ---- prompts layer ----

def test_system_prompt_interpolates_name():
    result = prompts.system_prompt({"name": "Zara"})
    assert "Zara" in result
    assert "Matt" not in result


def test_system_prompt_full_profile():
    result = prompts.system_prompt(_full("Zara"))
    assert "Zara" in result
    assert "Senior SWE" in result
    assert "strong cross-team relationships" in result
    assert "avoids conflict" in result
    assert "promoted to Staff" in result
    assert "direct, written-first" in result
    assert "300-person Series B" in result


def test_system_prompt_empty_optional_fields_no_none_text():
    result = prompts.system_prompt(_minimal("Min"))
    assert "None" not in result
    assert "Min" in result


def test_system_prompt_empty_dict_no_crash():
    result = prompts.system_prompt({})
    assert "the coached user" in result
    assert "None" not in result


def test_system_prompt_profile_block_omitted_when_sparse():
    result = prompts.system_prompt({"name": "Solo"})
    assert "[PROFILE" not in result


def test_system_prompt_profile_block_present_when_fields_set():
    result = prompts.system_prompt({"name": "Rich", "role": "EM", "coaching_goals": "VP in 5 years"})
    assert "[PROFILE" in result
    assert "coaching_goals" not in result   # label, not key
    assert "Coaching goals" in result


# ---- CLI: profile create ----

def test_cmd_profile_create_saves_row(temp_db, monkeypatch, capsys):
    answers = iter([
        "Alice",          # name
        "Staff Eng",      # role
        "BigCo, 500 eng", # org_context
        "good at writing",# strengths
        "hates conflict", # weaknesses
        "Staff in 1 yr",  # goals
        "terse, async",   # comm style
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    from snuscoach.cli import cmd_profile_create
    cmd_profile_create(None)

    out = capsys.readouterr().out
    assert "Profile created" in out
    assert "Alice" in out

    rows = db.list_user_profiles()
    assert len(rows) == 1
    p = rows[0]
    assert p["name"] == "Alice"
    assert p["role"] == "Staff Eng"
    assert p["org_context"] == "BigCo, 500 eng"
    assert p["political_strengths"] == "good at writing"
    assert p["political_weaknesses"] == "hates conflict"
    assert p["coaching_goals"] == "Staff in 1 yr"
    assert p["communication_style"] == "terse, async"


def test_cmd_profile_create_optional_fields_empty(temp_db, monkeypatch, capsys):
    answers = iter(["OnlyName", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    from snuscoach.cli import cmd_profile_create
    cmd_profile_create(None)

    p = db.list_user_profiles()[0]
    assert p["name"] == "OnlyName"
    assert p["role"] is None
    assert p["org_context"] is None


def test_cmd_profile_create_empty_name_exits(temp_db, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    from snuscoach.cli import cmd_profile_create
    with pytest.raises(SystemExit):
        cmd_profile_create(None)


# ---- CLI: profile list ----

def test_cmd_profile_list_empty(temp_db, capsys):
    from snuscoach.cli import cmd_profile_list
    cmd_profile_list(None)
    out = capsys.readouterr().out
    assert "No profiles yet" in out


def test_cmd_profile_list_shows_entries(temp_db, capsys):
    db.add_user_profile({"name": "First", "role": "SWE", "org_context": None,
                          "political_strengths": None, "political_weaknesses": None,
                          "coaching_goals": None, "communication_style": None})
    db.add_user_profile({"name": "Second", "role": None, "org_context": None,
                          "political_strengths": None, "political_weaknesses": None,
                          "coaching_goals": None, "communication_style": None})
    from snuscoach.cli import cmd_profile_list
    cmd_profile_list(None)
    out = capsys.readouterr().out
    assert "First" in out
    assert "Second" in out
    assert "(default)" in out
    # Only first profile should be marked default
    assert out.count("(default)") == 1


# ---- CLI: profile show ----

def test_cmd_profile_show(temp_db, capsys):
    pid = db.add_user_profile(_full("ShowMe"))
    from snuscoach.cli import cmd_profile_show

    class Args:
        id = pid

    cmd_profile_show(Args())
    out = capsys.readouterr().out
    assert "ShowMe" in out
    assert "Senior SWE" in out
    assert "strong cross-team relationships" in out


def test_cmd_profile_show_missing_exits(temp_db):
    from snuscoach.cli import cmd_profile_show

    class Args:
        id = 9999

    with pytest.raises(SystemExit):
        cmd_profile_show(Args())


def test_cmd_profile_show_none_fields_omitted(temp_db, capsys):
    pid = db.add_user_profile(_minimal("Sparse"))
    from snuscoach.cli import cmd_profile_show

    class Args:
        id = pid

    cmd_profile_show(Args())
    out = capsys.readouterr().out
    assert "None" not in out
    assert "Sparse" in out


# ---- _ensure_active_profile ----

def test_ensure_profile_creates_when_none_exist(temp_db, monkeypatch, capsys):
    answers = iter(["AutoUser", "SWE", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    from snuscoach.cli import _ensure_active_profile
    _ensure_active_profile()
    assert db.list_user_profiles()[0]["name"] == "AutoUser"


def test_ensure_profile_no_interview_when_exists(temp_db, monkeypatch):
    db.add_user_profile(_minimal("Existing"))
    called = []
    monkeypatch.setattr("builtins.input", lambda _: called.append(True) or "")
    from snuscoach.cli import _ensure_active_profile
    _ensure_active_profile()
    assert called == []


def test_ensure_profile_env_var_found(temp_db, monkeypatch):
    db.add_user_profile(_minimal("EnvUser"))
    monkeypatch.setenv("SNUSCOACH_PROFILE", "EnvUser")
    from snuscoach.cli import _ensure_active_profile
    _ensure_active_profile()  # should not raise


def test_ensure_profile_env_var_not_found_exits(temp_db, monkeypatch):
    monkeypatch.setenv("SNUSCOACH_PROFILE", "Ghost")
    from snuscoach.cli import _ensure_active_profile
    with pytest.raises(SystemExit) as exc_info:
        _ensure_active_profile()
    assert "Ghost" in str(exc_info.value)


def test_ensure_profile_missing_schema_exits(temp_db_path, monkeypatch):
    # temp_db_path fixture gives us a path with no schema (no init_db called)
    monkeypatch.setenv("SNUSCOACH_DB", str(temp_db_path))
    from snuscoach import cli
    with pytest.raises(SystemExit) as exc_info:
        cli._ensure_active_profile()
    assert "not initialized" in str(exc_info.value).lower()
