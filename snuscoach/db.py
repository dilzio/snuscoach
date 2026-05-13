import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".snuscoach" / "snuscoach.db"


def db_path() -> Path:
    return Path(os.environ.get("SNUSCOACH_DB", str(DEFAULT_DB_PATH)))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _is_old_schema(path: Path) -> bool:
    """Old schema = `meetings` exists with a `happened_at` column."""
    if not path.exists():
        return False
    conn = sqlite3.connect(path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(meetings)").fetchall()}
        return "happened_at" in cols
    finally:
        conn.close()


def _backup_db(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.parent / f"{path.name}.backup-{stamp}"
    shutil.copy2(path, backup)
    return backup


def init_db() -> None:
    path = db_path()
    needs_migration = _is_old_schema(path)
    if needs_migration:
        backup = _backup_db(path)
        print(f"Backed up DB to {backup} before migration.", file=sys.stderr)

    with connect() as conn:
        if needs_migration:
            _migrate_to_meeting_centric(conn)
        _ensure_schema(conn)
        _ensure_post_win_id(conn)


def _ensure_post_win_id(conn: sqlite3.Connection) -> None:
    """Additive migration: add win_id to posts if the column is absent."""
    try:
        conn.execute(
            "ALTER TABLE posts ADD COLUMN"
            " win_id INTEGER REFERENCES wins(id) ON DELETE SET NULL"
        )
    except Exception:
        pass  # column already exists — safe to ignore


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent CREATE for the current schema. Safe to run on a clean or
    already-migrated DB."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stakeholders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            role TEXT,
            relationship TEXT,
            communication_style TEXT,
            what_they_reward TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            channel TEXT NOT NULL,
            audience TEXT,
            posted_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            win_id INTEGER REFERENCES wins(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS meeting_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id INTEGER REFERENCES meeting_series(id),
            title TEXT NOT NULL,
            attendees TEXT,
            date TEXT NOT NULL,
            prep_context TEXT,
            prep_brief TEXT,
            debrief_notes TEXT,
            debrief_summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS voice_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_profiles (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            role                 TEXT,
            org_context          TEXT,
            political_strengths  TEXT,
            political_weaknesses TEXT,
            coaching_goals       TEXT,
            communication_style  TEXT,
            created_at           TEXT NOT NULL,
            updated_at           TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reflections (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT NOT NULL,
            since_date TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            content      TEXT    NOT NULL,
            coach_prompt TEXT,
            entry_type   TEXT    NOT NULL DEFAULT 'journal',
            created_at   TEXT    NOT NULL,
            updated_at   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nudges (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            report     TEXT NOT NULL,
            gaps_json  TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_threads (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id  INTEGER NOT NULL REFERENCES chat_threads(id),
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _migrate_to_meeting_centric(conn: sqlite3.Connection) -> None:
    """One-shot migration from (meetings + prep_briefs) to (meetings + meeting_series).

    Old `meetings`: id, title, attendees, purpose, notes, created_at, happened_at, coach_summary
    Old `prep_briefs`: id, title, attendees, context, brief, prep_for, created_at

    New `meetings`: id, series_id, title, attendees, date, prep_context, prep_brief,
                    debrief_notes, debrief_summary, created_at, updated_at

    Strategy: rename old `meetings` to `meetings_old`, create new tables, copy data,
    fold prep_briefs into matching meetings (by title + |date_diff| ≤ 7d) or insert
    as prep-only rows, then drop old tables.
    """
    has_prep_briefs = bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prep_briefs'"
        ).fetchone()
    )

    conn.execute("BEGIN")
    try:
        # 1. Rename old meetings out of the way
        conn.execute("ALTER TABLE meetings RENAME TO meetings_old")

        # 2. Create new schema (series + new meetings)
        conn.execute(
            """
            CREATE TABLE meeting_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER REFERENCES meeting_series(id),
                title TEXT NOT NULL,
                attendees TEXT,
                date TEXT NOT NULL,
                prep_context TEXT,
                prep_brief TEXT,
                debrief_notes TEXT,
                debrief_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # 3. Copy old meetings rows into new meetings
        conn.execute(
            """
            INSERT INTO meetings
                (id, title, attendees, date, debrief_notes, debrief_summary,
                 created_at, updated_at)
            SELECT id, title, attendees, happened_at, notes, coach_summary,
                   created_at, created_at
            FROM meetings_old
            WHERE happened_at IS NOT NULL
            """
        )

        # 4. Fold prep_briefs into meetings
        if has_prep_briefs:
            briefs = conn.execute(
                "SELECT id, title, attendees, context, brief, prep_for, created_at "
                "FROM prep_briefs"
            ).fetchall()
            for b in briefs:
                # Try to match an existing meeting: same title, date within ±7 days
                match = conn.execute(
                    """
                    SELECT id FROM meetings
                    WHERE title = ?
                      AND ABS(julianday(date) - julianday(?)) <= 7
                      AND prep_brief IS NULL
                    ORDER BY ABS(julianday(date) - julianday(?))
                    LIMIT 1
                    """,
                    (b[1], b[5], b[5]),
                ).fetchone()
                if match:
                    conn.execute(
                        "UPDATE meetings SET prep_context = ?, prep_brief = ?, "
                        "updated_at = ? WHERE id = ?",
                        (b[3], b[4], _now(), match[0]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO meetings
                             (title, attendees, date, prep_context, prep_brief,
                              created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (b[1], b[2], b[5], b[3], b[4], b[6], _now()),
                    )

        # 5. Drop old tables
        conn.execute("DROP TABLE meetings_old")
        if has_prep_briefs:
            conn.execute("DROP TABLE prep_briefs")

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ---- stakeholders ----

def add_stakeholder(profile: dict) -> int:
    defaults = {"role": None, "relationship": None, "communication_style": None, "what_they_reward": None, "notes": None}
    row = {**defaults, **profile}
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO stakeholders
                 (name, role, relationship, communication_style, what_they_reward, notes, created_at, updated_at)
               VALUES
                 (:name, :role, :relationship, :communication_style, :what_they_reward, :notes, :now, :now)""",
            {**row, "now": _now()},
        )
        return cur.lastrowid


def list_stakeholders() -> list:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM stakeholders ORDER BY name").fetchall())


def get_stakeholder(name: str):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM stakeholders WHERE name = ?", (name,)
        ).fetchone()


def update_stakeholder(name: str, **fields) -> None:
    allowed = {"role", "relationship", "communication_style", "what_they_reward", "notes"}
    sets: list = []
    args: list = []
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"unknown field: {k}")
        sets.append(f"{k} = ?")
        args.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    args.append(_now())
    args.append(name)
    with connect() as conn:
        conn.execute(f"UPDATE stakeholders SET {', '.join(sets)} WHERE name = ?", args)


def delete_stakeholder(stakeholder_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM stakeholders WHERE id = ?", (stakeholder_id,))


# ---- wins ----

def add_win(title: str, description: str | None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO wins (title, description, created_at) VALUES (?, ?, ?)",
            (title, description, _now()),
        )
        return cur.lastrowid


def list_wins() -> list:
    with connect() as conn:
        return list(
            conn.execute("SELECT * FROM wins ORDER BY created_at DESC").fetchall()
        )


# ---- posts ----

def add_post(
    content: str,
    channel: str,
    audience: str | None,
    posted_at: str,
    win_id: int | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO posts (content, channel, audience, posted_at, created_at, win_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content, channel, audience, posted_at, _now(), win_id),
        )
        return cur.lastrowid


def update_post(
    post_id: int,
    content: str,
    channel: str,
    audience: str | None,
    posted_at: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """UPDATE posts
               SET content = ?, channel = ?, audience = ?, posted_at = ?
               WHERE id = ?""",
            (content, channel, audience, posted_at, post_id),
        )


def list_posts() -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM posts ORDER BY posted_at DESC, id DESC"
            ).fetchall()
        )


# ---- meeting series ----

def add_meeting_series(name: str, description: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO meeting_series (name, description, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (name, description, _now(), _now()),
        )
        return cur.lastrowid


def list_meeting_series() -> list:
    with connect() as conn:
        return list(
            conn.execute("SELECT * FROM meeting_series ORDER BY name").fetchall()
        )


def get_meeting_series(series_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM meeting_series WHERE id = ?", (series_id,)
        ).fetchone()


def get_meeting_series_by_name(name: str):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM meeting_series WHERE name = ?", (name,)
        ).fetchone()


def update_meeting_series(
    series_id: int, name: str | None = None, description: str | None = None
) -> None:
    sets = []
    args: list = []
    if name is not None:
        sets.append("name = ?")
        args.append(name)
    if description is not None:
        sets.append("description = ?")
        args.append(description)
    if not sets:
        return
    sets.append("updated_at = ?")
    args.append(_now())
    args.append(series_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE meeting_series SET {', '.join(sets)} WHERE id = ?", args
        )


# ---- meetings ----

def add_meeting(
    title: str,
    date: str,
    attendees: str | None = None,
    series_id: int | None = None,
    prep_context: str | None = None,
    prep_brief: str | None = None,
    debrief_notes: str | None = None,
    debrief_summary: str | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO meetings
                 (series_id, title, attendees, date, prep_context, prep_brief,
                  debrief_notes, debrief_summary, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                series_id,
                title,
                attendees,
                date,
                prep_context,
                prep_brief,
                debrief_notes,
                debrief_summary,
                _now(),
                _now(),
            ),
        )
        return cur.lastrowid


def update_meeting(meeting_id: int, **fields) -> None:
    """Update arbitrary fields on a meeting. Pass any subset of: title,
    attendees, date, series_id, prep_context, prep_brief, debrief_notes,
    debrief_summary."""
    allowed = {
        "title",
        "attendees",
        "date",
        "series_id",
        "prep_context",
        "prep_brief",
        "debrief_notes",
        "debrief_summary",
    }
    sets = []
    args: list = []
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"unknown field: {k}")
        sets.append(f"{k} = ?")
        args.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    args.append(_now())
    args.append(meeting_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE meetings SET {', '.join(sets)} WHERE id = ?", args
        )


def list_meetings(limit: int = 50) -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM meetings ORDER BY date DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )


def list_meetings_by_series(series_id: int) -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM meetings WHERE series_id = ? ORDER BY date DESC, id DESC",
                (series_id,),
            ).fetchall()
        )


def get_meeting(meeting_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()


def delete_meeting(meeting_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))


# ---- voice samples ----

def add_voice_sample(content: str, description: str | None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO voice_samples (content, description, created_at) VALUES (?, ?, ?)",
            (content, description, _now()),
        )
        return cur.lastrowid


def list_voice_samples() -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM voice_samples ORDER BY created_at DESC, id DESC"
            ).fetchall()
        )


def get_voice_sample(sample_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM voice_samples WHERE id = ?", (sample_id,)
        ).fetchone()


def delete_voice_sample(sample_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM voice_samples WHERE id = ?", (sample_id,))
        return cur.rowcount > 0


# ---- user profiles ----

def add_user_profile(profile: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO user_profiles
                 (name, role, org_context, political_strengths, political_weaknesses,
                  coaching_goals, communication_style, created_at, updated_at)
               VALUES
                 (:name, :role, :org_context, :political_strengths, :political_weaknesses,
                  :coaching_goals, :communication_style, :now, :now)""",
            {**profile, "now": _now()},
        )
        return cur.lastrowid


def list_user_profiles() -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM user_profiles ORDER BY created_at ASC, id ASC"
            ).fetchall()
        )


def get_user_profile(profile_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM user_profiles WHERE id = ?", (profile_id,)
        ).fetchone()


def get_user_profile_by_name(name: str):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM user_profiles WHERE name = ?", (name,)
        ).fetchone()


def get_default_profile():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM user_profiles ORDER BY created_at ASC, id ASC LIMIT 1"
        ).fetchone()


# ---- reflections ----

def save_reflection(content: str, since_date: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reflections (content, since_date, created_at) VALUES (?, ?, ?)",
            (content, since_date, _now()),
        )
        return cur.lastrowid


def get_reflections(limit: int = 10) -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM reflections ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )


def get_latest_reflection():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM reflections ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()


# ---- journal entries ----

def add_journal_entry(
    content: str, coach_prompt: str | None = None, entry_type: str = "journal"
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO journal_entries
                 (content, coach_prompt, entry_type, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (content, coach_prompt, entry_type, _now(), _now()),
        )
        return cur.lastrowid


def list_journal_entries(limit: int = 10) -> list:
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM journal_entries ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )


def get_latest_journal_entry():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM journal_entries ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()


def add_nudge(date: str, report: str, gaps_json: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO nudges (date, report, gaps_json, created_at) VALUES (?, ?, ?, ?)",
            (date, report, gaps_json, _now()),
        )
        return cur.lastrowid


def get_nudge_for_date(date: str):
    """Return the most recent nudge row for the given YYYY-MM-DD date, or None.

    Returns None (rather than raising) if the nudges table does not yet exist
    so that callers degrade gracefully when the user hasn't run `make init`.
    """
    try:
        with connect() as conn:
            return conn.execute(
                "SELECT * FROM nudges WHERE date = ? ORDER BY id DESC LIMIT 1",
                (date,),
            ).fetchone()
    except Exception:
        return None


def get_latest_nudge():
    """Return the most recently created nudge row regardless of date, or None."""
    try:
        with connect() as conn:
            return conn.execute(
                "SELECT * FROM nudges ORDER BY id DESC LIMIT 1"
            ).fetchone()
    except Exception:
        return None


def get_or_create_thread(key: str) -> int:
    """Return the thread id for the given key, creating the row if absent."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM chat_threads WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO chat_threads (key, created_at, updated_at) VALUES (?, ?, ?)",
            (key, _now(), _now()),
        )
        return cur.lastrowid


def add_chat_message(thread_id: int, role: str, content: str) -> int:
    with connect() as conn:
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (_now(), thread_id),
        )
        cur = conn.execute(
            "INSERT INTO chat_messages (thread_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (thread_id, role, content, _now()),
        )
        return cur.lastrowid


def list_chat_messages(thread_id: int) -> list[dict]:
    """Return all messages for a thread in chronological order.

    Returns [] gracefully if the tables are absent (user hasn't run make init).
    """
    try:
        with connect() as conn:
            return conn.execute(
                "SELECT role, content FROM chat_messages"
                " WHERE thread_id = ? ORDER BY id ASC",
                (thread_id,),
            ).fetchall()
    except Exception:
        return []


def purge_canned_responses() -> dict:
    """Delete or null-out all DB rows containing the canned response marker.

    Meetings are preserved — only LLM-generated fields (prep_brief,
    debrief_summary) are cleared. Chat threads that contain any canned
    message are fully deleted (messages first to satisfy the FK constraint).
    """
    marker = "%[CANNED RESPONSE]%"
    counts: dict[str, int] = {}
    with connect() as conn:
        cur = conn.execute("DELETE FROM posts WHERE content LIKE ?", (marker,))
        counts["posts"] = cur.rowcount

        cur = conn.execute("DELETE FROM reflections WHERE content LIKE ?", (marker,))
        counts["reflections"] = cur.rowcount

        cur = conn.execute(
            "DELETE FROM journal_entries WHERE content LIKE ? OR coach_prompt LIKE ?",
            (marker, marker),
        )
        counts["journal_entries"] = cur.rowcount

        cur = conn.execute("DELETE FROM nudges WHERE report LIKE ?", (marker,))
        counts["nudges"] = cur.rowcount

        cur = conn.execute(
            "UPDATE meetings SET prep_brief = NULL, debrief_summary = NULL"
            " WHERE prep_brief LIKE ? OR debrief_summary LIKE ?",
            (marker, marker),
        )
        counts["meetings_cleared"] = cur.rowcount

        canned_rows = conn.execute(
            "SELECT DISTINCT thread_id FROM chat_messages WHERE content LIKE ?",
            (marker,),
        ).fetchall()
        if canned_rows:
            ids = [r[0] for r in canned_rows]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"DELETE FROM chat_messages WHERE thread_id IN ({placeholders})", ids
            )
            conn.execute(
                f"DELETE FROM chat_threads WHERE id IN ({placeholders})", ids
            )
        counts["chat_threads"] = len(canned_rows)

    return counts
