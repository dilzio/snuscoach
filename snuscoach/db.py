import os
import sqlite3
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
    return conn


def init_db() -> None:
    with connect() as conn:
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

            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                attendees TEXT,
                purpose TEXT,
                notes TEXT,
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
            """
        )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def add_meeting(title: str, attendees: str, purpose: str, notes: str = "") -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO meetings (title, attendees, purpose, notes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (title, attendees, purpose, notes, _now()),
        )
        return cur.lastrowid
