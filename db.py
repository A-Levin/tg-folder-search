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
            saved_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_status(link: str) -> str | None:
    with get_db() as conn:
        row = conn.execute("SELECT status FROM vacancies WHERE link = ?", (link,)).fetchone()
        return row["status"] if row else None


def set_status(link: str, status: str) -> None:
    with get_db() as conn:
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
            "SELECT link, saved_at FROM vacancies WHERE status = 'favorite' ORDER BY saved_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
