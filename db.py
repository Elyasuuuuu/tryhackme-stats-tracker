import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "stats.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TEXT NOT NULL,
                username TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_snapshot(username: str, payload: dict) -> int:
    init_db()
    collected_at = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO snapshots (collected_at, username, payload) VALUES (?, ?, ?)",
            (collected_at, username, json.dumps(payload)),
        )
        conn.commit()
        return int(cur.lastrowid)


def latest_snapshot(username: str | None = None) -> dict | None:
    init_db()
    with connect() as conn:
        if username:
            row = conn.execute(
                """
                SELECT collected_at, username, payload
                FROM snapshots
                WHERE username = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (username,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT collected_at, username, payload
                FROM snapshots
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
    if not row:
        return None
    return {
        "collected_at": row["collected_at"],
        "username": row["username"],
        "data": json.loads(row["payload"]),
    }


def history(username: str, limit: int = 20) -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT collected_at, payload
            FROM snapshots
            WHERE username = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (username, limit),
        ).fetchall()
    return [
        {"collected_at": row["collected_at"], "data": json.loads(row["payload"])}
        for row in rows
    ]
