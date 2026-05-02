"""CLI integration tests: argparse dispatch, end-to-end init via subprocess.

Drives the installed `snuscoach` console script as a subprocess so we exercise
the same path the user does. No API calls.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest


SNUSCOACH = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "snuscoach"


def _run(args, env_overrides=None, **kwargs):
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(SNUSCOACH), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        **kwargs,
    )


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Override the auto temp_db fixture for subprocess tests — children read SNUSCOACH_DB from env."""
    return tmp_path / "snuscoach.db"


@pytest.mark.skipif(
    not SNUSCOACH.exists(),
    reason="snuscoach binary not installed; run `make install` first",
)
class TestCliDispatch:
    def test_top_level_help(self, isolated_db):
        r = _run(["--help"], {"SNUSCOACH_DB": str(isolated_db)})
        assert r.returncode == 0
        # Every top-level subcommand should appear in help
        for cmd in [
            "init",
            "stakeholder",
            "win",
            "post",
            "prep",
            "debrief",
            "meeting",
            "series",
            "chat",
        ]:
            assert cmd in r.stdout, f"missing {cmd} in help: {r.stdout}"

    @pytest.mark.parametrize(
        "args",
        [
            ["init", "--help"],
            ["stakeholder", "--help"],
            ["stakeholder", "add", "--help"],
            ["stakeholder", "list", "--help"],
            ["stakeholder", "show", "--help"],
            ["win", "--help"],
            ["win", "add", "--help"],
            ["win", "list", "--help"],
            ["post", "--help"],
            ["post", "draft", "--help"],
            ["post", "list", "--help"],
            ["prep", "--help"],
            ["debrief", "--help"],
            ["meeting", "--help"],
            ["meeting", "create", "--help"],
            ["meeting", "prep", "--help"],
            ["meeting", "debrief", "--help"],
            ["meeting", "edit", "--help"],
            ["meeting", "list", "--help"],
            ["meeting", "show", "--help"],
            ["series", "--help"],
            ["series", "add", "--help"],
            ["series", "list", "--help"],
            ["series", "show", "--help"],
            ["series", "edit", "--help"],
            ["chat", "--help"],
        ],
    )
    def test_subcommand_help(self, args, isolated_db):
        r = _run(args, {"SNUSCOACH_DB": str(isolated_db)})
        assert r.returncode == 0, f"{args} failed:\n{r.stderr}"

    def test_init_creates_db_and_lists_show_empty(self, isolated_db):
        env = {"SNUSCOACH_DB": str(isolated_db)}

        r = _run(["init"], env)
        assert r.returncode == 0
        assert isolated_db.exists()

        # Empty list paths should all exit 0 with a "no X yet" message
        for args in [
            ["stakeholder", "list"],
            ["win", "list"],
            ["post", "list"],
            ["meeting", "list"],
            ["series", "list"],
        ]:
            r = _run(args, env)
            assert r.returncode == 0, f"{args} failed: {r.stderr}"

    def test_meeting_show_missing_id_exits_nonzero(self, isolated_db):
        _run(["init"], {"SNUSCOACH_DB": str(isolated_db)})
        r = _run(
            ["meeting", "show", "9999"],
            {"SNUSCOACH_DB": str(isolated_db)},
        )
        assert r.returncode != 0
        assert "No meeting" in r.stderr or "No meeting" in r.stdout
