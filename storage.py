"""SQLite persistence for idempotent processing and audit state."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    action TEXT,
                    status TEXT NOT NULL,
                    detail TEXT,
                    received_at TEXT,
                    processed_at TEXT NOT NULL,
                    reply_message_id TEXT
                );
                CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def has_message(self, message_id: str) -> bool:
        with self._connection() as db:
            return db.execute(
                "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
            ).fetchone() is not None

    def record_message(
        self, message_id: str, sender: str, subject: str, status: str,
        action: str | None = None, detail: str = "", received_at: str = "",
    ) -> bool:
        with self._connection() as db:
            existing = db.execute(
                "SELECT status FROM processed_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if existing is not None:
                if existing["status"] != "error":
                    return False
                db.execute(
                    """UPDATE processed_messages SET sender=?, subject=?, action=?,
                    status=?, detail=?, received_at=?, processed_at=?,
                    reply_message_id=NULL WHERE message_id=?""",
                    (sender, subject, action, status, detail, received_at, utc_now(), message_id),
                )
                return True
            cursor = db.execute(
                """INSERT OR IGNORE INTO processed_messages
                (message_id, sender, subject, action, status, detail, received_at, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (message_id, sender, subject, action, status, detail, received_at, utc_now()),
            )
            return cursor.rowcount == 1

    def update_message(self, message_id: str, status: str, detail: str = "",
                       reply_message_id: str | None = None) -> None:
        with self._connection() as db:
            db.execute(
                """UPDATE processed_messages SET status=?, detail=?, processed_at=?,
                reply_message_id=COALESCE(?, reply_message_id) WHERE message_id=?""",
                (status, detail, utc_now(), reply_message_id, message_id),
            )

    def log_action(self, message_id: str, action: str, status: str, detail: str = "") -> None:
        with self._connection() as db:
            db.execute(
                "INSERT INTO action_log (message_id, action, status, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (message_id, action, status, detail, utc_now()),
            )

    def get_status_counts(self) -> dict[str, int]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT status, COUNT(*) AS count FROM processed_messages GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def get_message(self, message_id: str) -> sqlite3.Row | None:
        with self._connection() as db:
            return db.execute(
                "SELECT * FROM processed_messages WHERE message_id=?", (message_id,)
            ).fetchone()
