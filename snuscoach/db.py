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
            created_at TEXT NOT NULL
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
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO stakeholders
                 (name, role, relationship, communication_style, what_they_reward, notes, created_at, updated_at)
               VALUES
                 (:name, :role, :relationship, :communication_style, :what_they_reward, :notes, :now, :now)""",
            {**profile, "now": _now()},
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
    content: str, channel: str, audience: str | None, posted_at: str
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO posts (content, channel, audience, posted_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (content, channel, audience, posted_at, _now()),
        )
        return cur.lastrowid


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
