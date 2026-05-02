"""Integration tests for the SQLite layer.

Real SQLite, real schema (per-test temp DB via conftest fixture). No mocks.
"""
from snuscoach import db


def test_init_creates_all_tables(temp_db):
    with db.connect() as conn:
        names = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"stakeholders", "wins", "meetings", "posts", "prep_briefs"} <= names


def test_meetings_schema_has_debrief_columns(temp_db):
    """`debrief` writes to happened_at and coach_summary; ensure migration ran."""
    with db.connect() as conn:
        cols = {
            r["name"]
            for r in conn.execute("PRAGMA table_info(meetings)").fetchall()
        }
    assert "happened_at" in cols
    assert "coach_summary" in cols
    assert "notes" in cols


def test_stakeholder_round_trip(temp_db):
    sid = db.add_stakeholder(
        {
            "name": "Sarah Chen",
            "role": "VP Eng",
            "relationship": "skip",
            "communication_style": "terse, data-driven",
            "what_they_reward": "clear ownership",
            "notes": "New to org Q1.",
        }
    )
    assert sid > 0
    rows = db.list_stakeholders()
    assert len(rows) == 1
    assert rows[0]["name"] == "Sarah Chen"

    s = db.get_stakeholder("Sarah Chen")
    assert s["relationship"] == "skip"
    assert s["what_they_reward"] == "clear ownership"


def test_win_round_trip(temp_db):
    wid = db.add_win("Shipped X", "Cut p99 latency by 40%")
    assert wid > 0
    rows = db.list_wins()
    assert len(rows) == 1
    assert rows[0]["title"] == "Shipped X"
    assert rows[0]["description"] == "Cut p99 latency by 40%"


def test_post_round_trip(temp_db):
    pid = db.add_post(
        content="We shipped the migration.",
        channel="Slack #engineering",
        audience="team-broadcast",
        posted_at="2026-04-30",
    )
    assert pid > 0
    rows = db.list_posts()
    assert len(rows) == 1
    assert rows[0]["channel"] == "Slack #engineering"
    assert rows[0]["posted_at"] == "2026-04-30"


def test_meeting_round_trip(temp_db):
    mid = db.add_meeting(
        title="1:1 with Sarah",
        attendees="Sarah Chen",
        notes="She wants me to take the platform reorg.",
        coach_summary="Follow-up: send proposal by Friday.",
        happened_at="2026-05-01",
    )
    assert mid > 0

    rows = db.list_meetings()
    assert len(rows) == 1
    assert rows[0]["title"] == "1:1 with Sarah"
    assert rows[0]["happened_at"] == "2026-05-01"
    assert rows[0]["coach_summary"] == "Follow-up: send proposal by Friday."

    m = db.get_meeting(mid)
    assert m["notes"] == "She wants me to take the platform reorg."


def test_meeting_list_orders_by_happened_at_desc(temp_db):
    db.add_meeting("Older", None, "n1", "s1", "2026-04-15")
    db.add_meeting("Newer", None, "n2", "s2", "2026-05-01")
    db.add_meeting("Middle", None, "n3", "s3", "2026-04-20")
    titles = [r["title"] for r in db.list_meetings()]
    assert titles == ["Newer", "Middle", "Older"]


def test_meeting_attendees_optional(temp_db):
    mid = db.add_meeting("Solo think", None, "thinking", "next steps", "2026-05-01")
    m = db.get_meeting(mid)
    assert m["attendees"] is None


def test_get_meeting_returns_none_for_missing_id(temp_db):
    assert db.get_meeting(9999) is None


def test_prep_brief_round_trip(temp_db):
    bid = db.add_prep_brief(
        title="1:1 with Frekus",
        attendees="Matt, Frekus",
        context="Architecture buy-in update.",
        brief="Lead with the outcome. Tie to acquisition integration.",
        prep_for="2026-05-05",
    )
    assert bid > 0

    rows = db.list_prep_briefs()
    assert len(rows) == 1
    assert rows[0]["title"] == "1:1 with Frekus"
    assert rows[0]["prep_for"] == "2026-05-05"
    assert rows[0]["brief"].startswith("Lead with the outcome")

    b = db.get_prep_brief(bid)
    assert b["context"] == "Architecture buy-in update."


def test_prep_brief_list_orders_by_prep_for_desc(temp_db):
    db.add_prep_brief("Older", None, None, "b1", "2026-04-15")
    db.add_prep_brief("Newer", None, None, "b2", "2026-05-10")
    db.add_prep_brief("Middle", None, None, "b3", "2026-04-25")
    titles = [r["title"] for r in db.list_prep_briefs()]
    assert titles == ["Newer", "Middle", "Older"]


def test_prep_brief_optional_fields(temp_db):
    bid = db.add_prep_brief("Solo think", None, None, "brief content", "2026-05-01")
    b = db.get_prep_brief(bid)
    assert b["attendees"] is None
    assert b["context"] is None
    assert b["brief"] == "brief content"


def test_get_prep_brief_returns_none_for_missing_id(temp_db):
    assert db.get_prep_brief(9999) is None
