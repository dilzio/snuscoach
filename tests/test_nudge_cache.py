"""Tests for nudge caching: DB layer and CLI integration.

Verifies that:
- add_nudge / get_nudge_for_date round-trip correctly
- get_nudge_for_date returns None for a different date and when the table is absent
- _nudge_report() persists the LLM output to the nudges table
- _nudge_report() is skipped when no gaps exist (no nudge row created)
"""

import json
from unittest.mock import patch

import pytest

from snuscoach import db
from snuscoach.cli import _compute_nudge_gaps, _nudge_report


# ---------------------------------------------------------------------------
# DB layer
# ---------------------------------------------------------------------------


def test_add_and_retrieve_nudge(temp_db):
    nid = db.add_nudge("2026-05-08", "Here is your nudge report.", '{"key": 1}')
    assert isinstance(nid, int)

    row = db.get_nudge_for_date("2026-05-08")
    assert row is not None
    assert row["report"] == "Here is your nudge report."
    assert row["gaps_json"] == '{"key": 1}'
    assert row["date"] == "2026-05-08"


def test_get_nudge_returns_none_for_other_date(temp_db):
    db.add_nudge("2026-05-08", "Today's nudge.")
    assert db.get_nudge_for_date("2026-05-07") is None
    assert db.get_nudge_for_date("2026-05-09") is None


def test_get_nudge_latest_when_multiple_rows(temp_db):
    db.add_nudge("2026-05-08", "First nudge.")
    db.add_nudge("2026-05-08", "Second nudge.")
    row = db.get_nudge_for_date("2026-05-08")
    assert row["report"] == "Second nudge."


def test_get_latest_nudge_returns_most_recent_across_dates(temp_db):
    db.add_nudge("2026-05-07", "Yesterday's nudge.")
    db.add_nudge("2026-05-08", "Today's nudge.")
    row = db.get_latest_nudge()
    assert row is not None
    assert row["report"] == "Today's nudge."


def test_get_latest_nudge_returns_none_when_empty(temp_db):
    assert db.get_latest_nudge() is None


def test_get_latest_nudge_missing_table_returns_none(temp_db_path):
    assert db.get_latest_nudge() is None


def test_get_nudge_missing_table_returns_none(temp_db_path):
    """get_nudge_for_date returns None gracefully if nudges table doesn't exist."""
    # temp_db_path fixture sets SNUSCOACH_DB but does NOT call init_db,
    # so the DB file exists but has no tables yet.
    result = db.get_nudge_for_date("2026-05-08")
    assert result is None


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_nudge_report_persists_to_db(temp_db, monkeypatch):
    """_nudge_report() saves the LLM report to the nudges table."""
    gaps = {
        "undebriefed_meetings": [{"id": 1, "title": "1:1", "date": "2026-05-01"}],
        "wins_without_post": 0,
        "silent_stakeholders": [],
        "journal_gap_days": 999,
    }

    with patch("snuscoach.coach.draft", return_value="Mock nudge report") as mock_draft, \
         patch("builtins.input", return_value=""):  # skip action selection
        _nudge_report(gaps)

    mock_draft.assert_called_once()

    today = __import__("datetime").date.today().isoformat()
    row = db.get_nudge_for_date(today)
    assert row is not None
    assert row["report"] == "Mock nudge report"
    assert row["date"] == today
    stored_gaps = json.loads(row["gaps_json"])
    assert stored_gaps["undebriefed_meetings"][0]["title"] == "1:1"


def test_nudge_report_no_gaps_does_not_save(temp_db, capsys):
    """When there are no gaps, _nudge_report() prints a no-gap message and saves nothing."""
    gaps = {
        "undebriefed_meetings": [],
        "wins_without_post": 0,
        "silent_stakeholders": [],
        "journal_gap_days": 0,
    }

    with patch("snuscoach.coach.draft", return_value="unused") as mock_draft:
        _nudge_report(gaps)

    mock_draft.assert_not_called()

    today = __import__("datetime").date.today().isoformat()
    assert db.get_nudge_for_date(today) is None


def test_nudge_report_db_failure_does_not_raise(temp_db, capsys):
    """If db.add_nudge raises, _nudge_report() should not propagate the exception."""
    gaps = {
        "undebriefed_meetings": [{"id": 1, "title": "1:1", "date": "2026-05-01"}],
        "wins_without_post": 0,
        "silent_stakeholders": [],
        "journal_gap_days": 999,
    }

    with patch("snuscoach.coach.draft", return_value="Mock nudge report"), \
         patch("snuscoach.db.add_nudge", side_effect=Exception("DB exploded")), \
         patch("builtins.input", return_value=""):
        # Should not raise despite DB failure
        _nudge_report(gaps)

    # Warning should appear on stderr
    captured = capsys.readouterr()
    assert "make init" in captured.err
