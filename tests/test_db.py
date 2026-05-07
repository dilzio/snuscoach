"""Integration tests for the SQLite layer.

Real SQLite, real schema (per-test temp DB via conftest fixture). No mocks.
Includes a migration test that seeds the old (meetings + prep_briefs) schema
and asserts post-migration shape and data preservation.
"""
import pytest
import sqlite3

from snuscoach import db


# ---- schema sanity ----


def test_init_creates_all_tables(temp_db):
    with db.connect() as conn:
        names = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {
        "stakeholders",
        "wins",
        "posts",
        "meeting_series",
        "meetings",
        "journal_entries",
    } <= names
    # Old tables must be gone
    assert "prep_briefs" not in names


def test_meetings_schema_has_new_columns(temp_db):
    with db.connect() as conn:
        cols = {
            r["name"]
            for r in conn.execute("PRAGMA table_info(meetings)").fetchall()
        }
    assert {
        "id",
        "series_id",
        "title",
        "attendees",
        "date",
        "prep_context",
        "prep_brief",
        "debrief_notes",
        "debrief_summary",
        "created_at",
        "updated_at",
    } == cols


# ---- stakeholders / wins / posts (legacy CRUD round-trips, unchanged) ----


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
    assert db.get_stakeholder("Sarah Chen")["relationship"] == "skip"


def test_update_stakeholder_single_field(temp_db):
    db.add_stakeholder({"name": "Sarah Chen", "role": "VP Eng", "relationship": "skip"})
    db.update_stakeholder("Sarah Chen", role="CTO")
    s = db.get_stakeholder("Sarah Chen")
    assert s["role"] == "CTO"
    assert s["relationship"] == "skip"


def test_update_stakeholder_multiple_fields(temp_db):
    db.add_stakeholder({"name": "Sarah Chen", "role": "VP Eng"})
    db.update_stakeholder("Sarah Chen", role="CTO", notes="promoted in Q2")
    s = db.get_stakeholder("Sarah Chen")
    assert s["role"] == "CTO"
    assert s["notes"] == "promoted in Q2"


def test_update_stakeholder_updates_updated_at(temp_db):
    db.add_stakeholder({"name": "Sarah Chen", "role": "VP Eng"})
    before = db.get_stakeholder("Sarah Chen")["updated_at"]
    db.update_stakeholder("Sarah Chen", role="CTO")
    after = db.get_stakeholder("Sarah Chen")["updated_at"]
    assert after >= before


def test_update_stakeholder_rejects_unknown_field(temp_db):
    db.add_stakeholder({"name": "Sarah Chen"})
    with pytest.raises(ValueError, match="bogus"):
        db.update_stakeholder("Sarah Chen", bogus="x")


def test_update_stakeholder_noop_on_no_fields(temp_db):
    db.add_stakeholder({"name": "Sarah Chen", "role": "VP Eng"})
    db.update_stakeholder("Sarah Chen")
    assert db.get_stakeholder("Sarah Chen")["role"] == "VP Eng"


def test_win_round_trip(temp_db):
    wid = db.add_win("Shipped X", "Cut p99 by 40%")
    assert wid > 0
    assert db.list_wins()[0]["title"] == "Shipped X"


def test_post_round_trip(temp_db):
    pid = db.add_post(
        content="We shipped the migration.",
        channel="Slack #engineering",
        audience="team-broadcast",
        posted_at="2026-04-30",
    )
    assert pid > 0
    assert db.list_posts()[0]["channel"] == "Slack #engineering"


# ---- meeting series ----


def test_series_round_trip(temp_db):
    sid = db.add_meeting_series("1:1 with Sarah", "Weekly")
    assert sid > 0
    s = db.get_meeting_series(sid)
    assert s["name"] == "1:1 with Sarah"
    assert s["description"] == "Weekly"
    assert db.get_meeting_series_by_name("1:1 with Sarah")["id"] == sid


def test_series_unique_name(temp_db):
    db.add_meeting_series("Staff", None)
    try:
        db.add_meeting_series("Staff", None)
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("expected IntegrityError on duplicate series name")


def test_update_series(temp_db):
    sid = db.add_meeting_series("Old name", None)
    db.update_meeting_series(sid, name="New name", description="now with desc")
    s = db.get_meeting_series(sid)
    assert s["name"] == "New name"
    assert s["description"] == "now with desc"


# ---- meetings (new schema) ----


def test_meeting_round_trip_minimal(temp_db):
    mid = db.add_meeting(title="Solo think", date="2026-05-01")
    assert mid > 0
    m = db.get_meeting(mid)
    assert m["title"] == "Solo think"
    assert m["date"] == "2026-05-01"
    assert m["attendees"] is None
    assert m["series_id"] is None
    assert m["prep_brief"] is None
    assert m["debrief_summary"] is None


def test_meeting_round_trip_full(temp_db):
    sid = db.add_meeting_series("1:1 with Sarah", None)
    mid = db.add_meeting(
        title="1:1 with Sarah",
        date="2026-05-05",
        attendees="Matt, Sarah",
        series_id=sid,
        prep_context="reorg context",
        prep_brief="lead with outcome",
        debrief_notes="she pushed back",
        debrief_summary="follow-up: send proposal",
    )
    m = db.get_meeting(mid)
    assert m["series_id"] == sid
    assert m["prep_brief"] == "lead with outcome"
    assert m["debrief_summary"] == "follow-up: send proposal"


def test_meeting_list_orders_by_date_desc(temp_db):
    db.add_meeting("Older", date="2026-04-15")
    db.add_meeting("Newer", date="2026-05-10")
    db.add_meeting("Middle", date="2026-04-25")
    titles = [r["title"] for r in db.list_meetings()]
    assert titles == ["Newer", "Middle", "Older"]


def test_list_meetings_by_series(temp_db):
    s1 = db.add_meeting_series("S1", None)
    s2 = db.add_meeting_series("S2", None)
    db.add_meeting("a", "2026-05-01", series_id=s1)
    db.add_meeting("b", "2026-05-02", series_id=s2)
    db.add_meeting("c", "2026-05-03", series_id=s1)
    titles_s1 = [r["title"] for r in db.list_meetings_by_series(s1)]
    assert titles_s1 == ["c", "a"]


def test_update_meeting(temp_db):
    mid = db.add_meeting("title", "2026-05-01")
    db.update_meeting(mid, title="new title", prep_brief="brief")
    m = db.get_meeting(mid)
    assert m["title"] == "new title"
    assert m["prep_brief"] == "brief"
    # updated_at should change
    assert m["updated_at"]


def test_update_meeting_rejects_unknown_field(temp_db):
    mid = db.add_meeting("t", "2026-05-01")
    try:
        db.update_meeting(mid, bogus="x")
    except ValueError as e:
        assert "bogus" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_get_meeting_returns_none_for_missing_id(temp_db):
    assert db.get_meeting(9999) is None


def test_get_meeting_series_returns_none_for_missing_id(temp_db):
    assert db.get_meeting_series(9999) is None


# ---- migration test ----


def _seed_old_schema(path):
    """Seed an old-schema DB (meetings + prep_briefs) to exercise migration."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE stakeholders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            role TEXT, relationship TEXT, communication_style TEXT,
            what_they_reward TEXT, notes TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE wins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL, channel TEXT NOT NULL,
            audience TEXT, posted_at TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            attendees TEXT,
            purpose TEXT,
            notes TEXT,
            happened_at TEXT,
            coach_summary TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE prep_briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, attendees TEXT, context TEXT,
            brief TEXT NOT NULL, prep_for TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    return conn


def test_migration_from_old_schema(temp_db_path, monkeypatch):
    # Seed old schema with some meetings + prep_briefs that match and don't match
    conn = _seed_old_schema(temp_db_path)
    conn.executescript(
        """
        INSERT INTO meetings (title, attendees, notes, coach_summary, happened_at, created_at)
        VALUES ('1:1 with Sarah', 'Matt, Sarah', 'pushed back on reorg',
                'follow-up: send proposal', '2026-05-05', '2026-05-05T10:00:00');
        INSERT INTO meetings (title, attendees, notes, coach_summary, happened_at, created_at)
        VALUES ('Staff', 'team', 'Q2 plans', 'flag risk to skip', '2026-04-30', '2026-04-30T15:00:00');

        -- This prep_brief matches the Sarah meeting (same title, ±7 days)
        INSERT INTO prep_briefs (title, attendees, context, brief, prep_for, created_at)
        VALUES ('1:1 with Sarah', 'Matt, Sarah', 'reorg context',
                'lead with outcome', '2026-05-05', '2026-05-04T08:00:00');

        -- This one has no matching meeting → should become its own row
        INSERT INTO prep_briefs (title, attendees, context, brief, prep_for, created_at)
        VALUES ('1:1 with Frekus', 'Matt, Frekus', 'arch buy-in',
                'tie to acquisition', '2026-05-08', '2026-05-07T08:00:00');
        """
    )
    conn.commit()
    conn.close()

    # Run init → triggers migration
    db.init_db()

    # New tables exist, old prep_briefs is gone
    with db.connect() as new_conn:
        names = {
            r[0]
            for r in new_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "meeting_series" in names
    assert "prep_briefs" not in names
    assert "meetings_old" not in names

    # Schema is the new shape
    with db.connect() as new_conn:
        cols = {
            r["name"]
            for r in new_conn.execute("PRAGMA table_info(meetings)").fetchall()
        }
    assert "date" in cols
    assert "happened_at" not in cols
    assert "prep_brief" in cols
    assert "debrief_summary" in cols

    # Existing meeting rows preserved (debrief side)
    rows = db.list_meetings()
    assert len(rows) == 3  # 2 old meetings + 1 unmatched prep
    sarah = next(r for r in rows if r["title"] == "1:1 with Sarah")
    assert sarah["date"] == "2026-05-05"
    assert sarah["debrief_summary"] == "follow-up: send proposal"
    assert sarah["debrief_notes"] == "pushed back on reorg"
    # The matching prep_brief was folded into this row
    assert sarah["prep_brief"] == "lead with outcome"
    assert sarah["prep_context"] == "reorg context"

    staff = next(r for r in rows if r["title"] == "Staff")
    assert staff["debrief_summary"] == "flag risk to skip"
    assert staff["prep_brief"] is None  # no matching prep

    # Unmatched prep became its own meeting row
    frekus = next(r for r in rows if r["title"] == "1:1 with Frekus")
    assert frekus["date"] == "2026-05-08"
    assert frekus["prep_brief"] == "tie to acquisition"
    assert frekus["debrief_summary"] is None

    # Backup file should exist next to the DB
    backups = [
        p for p in temp_db_path.parent.iterdir() if p.name.startswith(temp_db_path.name + ".backup-")
    ]
    assert len(backups) == 1


# ---- reflections ----


def test_reflections_table_exists(temp_db):
    with db.connect() as conn:
        names = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "reflections" in names


def test_save_reflection_returns_id(temp_db):
    rid = db.save_reflection("Pattern brief content.")
    assert rid > 0


def test_get_latest_reflection_returns_most_recent(temp_db):
    db.save_reflection("First reflection")
    db.save_reflection("Second reflection")
    latest = db.get_latest_reflection()
    assert latest["content"] == "Second reflection"


def test_get_latest_reflection_returns_none_when_empty(temp_db):
    assert db.get_latest_reflection() is None


def test_save_reflection_stores_since_date(temp_db):
    db.save_reflection("Windowed brief", since_date="2026-04-01")
    r = db.get_latest_reflection()
    assert r["since_date"] == "2026-04-01"


def test_save_reflection_since_date_optional(temp_db):
    db.save_reflection("Full-history brief")
    r = db.get_latest_reflection()
    assert r["since_date"] is None


def test_get_reflections_returns_all(temp_db):
    db.save_reflection("A")
    db.save_reflection("B")
    db.save_reflection("C")
    rows = db.get_reflections(limit=10)
    assert len(rows) == 3


def test_get_reflections_respects_limit(temp_db):
    for i in range(5):
        db.save_reflection(f"Reflection {i}")
    rows = db.get_reflections(limit=2)
    assert len(rows) == 2


def test_get_reflections_orders_newest_first(temp_db):
    db.save_reflection("Oldest")
    db.save_reflection("Newest")
    rows = db.get_reflections(limit=10)
    assert rows[0]["content"] == "Newest"
    assert rows[-1]["content"] == "Oldest"


# ---- journal entries ----


def test_journal_entries_table_exists(temp_db):
    with db.connect() as conn:
        names = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "journal_entries" in names


def test_add_journal_entry_returns_id(temp_db):
    jid = db.add_journal_entry("Alice was terse in the 1:1.")
    assert jid > 0


def test_journal_entry_defaults(temp_db):
    db.add_journal_entry("Some notes.")
    entry = db.get_latest_journal_entry()
    assert entry["entry_type"] == "journal"
    assert entry["coach_prompt"] is None


def test_journal_entry_with_all_fields(temp_db):
    db.add_journal_entry("My response.", coach_prompt="Coach questions.", entry_type="nudge")
    entry = db.get_latest_journal_entry()
    assert entry["content"] == "My response."
    assert entry["coach_prompt"] == "Coach questions."
    assert entry["entry_type"] == "nudge"


def test_list_journal_entries_round_trip(temp_db):
    db.add_journal_entry("Entry A.")
    db.add_journal_entry("Entry B.")
    db.add_journal_entry("Entry C.")
    rows = db.list_journal_entries(limit=10)
    assert len(rows) == 3
    # Newest first
    assert rows[0]["content"] == "Entry C."
    assert rows[-1]["content"] == "Entry A."


def test_list_journal_entries_respects_limit(temp_db):
    for i in range(5):
        db.add_journal_entry(f"Entry {i}.")
    rows = db.list_journal_entries(limit=3)
    assert len(rows) == 3


def test_get_latest_journal_entry_returns_none_on_empty(temp_db):
    assert db.get_latest_journal_entry() is None


def test_get_latest_journal_entry_returns_most_recent(temp_db):
    db.add_journal_entry("First.")
    db.add_journal_entry("Second.")
    latest = db.get_latest_journal_entry()
    assert latest["content"] == "Second."


def test_journal_entries_added_after_migration(temp_db_path, monkeypatch):
    """journal_entries table is added when init_db is run on a DB that already
    has the current schema minus journal_entries (simulates upgrading an existing DB)."""
    import sqlite3

    # Create a DB with current tables minus journal_entries
    conn = sqlite3.connect(temp_db_path)
    conn.executescript(
        """
        CREATE TABLE stakeholders (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            role TEXT, relationship TEXT, communication_style TEXT, what_they_reward TEXT,
            notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE wins (id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            description TEXT, created_at TEXT NOT NULL);
        CREATE TABLE reflections (id INTEGER PRIMARY KEY, content TEXT NOT NULL,
            since_date TEXT, created_at TEXT NOT NULL);
        """
    )
    conn.commit()
    conn.close()

    # init_db should add journal_entries without error
    db.init_db()

    with db.connect() as c:
        names = {
            r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "journal_entries" in names

    # Existing data untouched
    jid = db.add_journal_entry("Post-migration entry.")
    assert jid > 0
