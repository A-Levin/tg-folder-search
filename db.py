import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.tg-folder-search.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vacancies (
            link TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            title TEXT,
            channel TEXT,
            date TEXT,
            salary TEXT,
            location TEXT,
            stack TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vacancies_new (
            link TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            title TEXT,
            channel TEXT,
            date TEXT,
            salary TEXT,
            location TEXT,
            stack TEXT
        )
    """)
    # migrate old table if missing columns
    try:
        conn.execute("ALTER TABLE vacancies ADD COLUMN title TEXT")
        conn.execute("ALTER TABLE vacancies ADD COLUMN channel TEXT")
        conn.execute("ALTER TABLE vacancies ADD COLUMN date TEXT")
        conn.execute("ALTER TABLE vacancies ADD COLUMN salary TEXT")
        conn.execute("ALTER TABLE vacancies ADD COLUMN location TEXT")
        conn.execute("ALTER TABLE vacancies ADD COLUMN stack TEXT")
    except Exception:
        pass
    conn.commit()
    return conn


def get_status(link: str) -> str | None:
    with get_db() as conn:
        row = conn.execute("SELECT status FROM vacancies WHERE link = ?", (link,)).fetchone()
        return row["status"] if row else None


def set_status(link: str, status: str, vacancy=None) -> None:
    with get_db() as conn:
        if vacancy:
            conn.execute(
                """INSERT OR REPLACE INTO vacancies
                   (link, status, saved_at, title, channel, date, salary, location, stack)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (link, status, datetime.now().isoformat(),
                 vacancy.title, vacancy.channel, vacancy.date,
                 vacancy.salary, vacancy.location, vacancy.stack),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO vacancies (link, status, saved_at) VALUES (?, ?, ?)",
                (link, status, datetime.now().isoformat()),
            )


def delete_status(link: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM vacancies WHERE link = ?", (link,))


def get_all_statuses() -> dict[str, str]:
    with get_db() as conn:
        rows = conn.execute("SELECT link, status FROM vacancies").fetchall()
        return {row["link"]: row["status"] for row in rows}


def get_favorites() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM vacancies WHERE status = 'favorite' ORDER BY saved_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
