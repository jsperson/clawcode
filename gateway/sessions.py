"""Session manager with SQLite WAL storage.

Manages gateway sessions — each session maps to a client connection and
a claude CLI subprocess. Sessions persist across gateway restarts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .protocol import ClientType, SessionStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    client_type TEXT NOT NULL,
    client_metadata TEXT DEFAULT '{}',
    claude_session_id TEXT,
    claude_pid INTEGER,
    created_at REAL NOT NULL,
    last_activity REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT,
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
"""


# ---------------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------------


@dataclass
class Session:
    id: str
    client_type: ClientType
    client_metadata: dict
    claude_session_id: str | None
    claude_pid: int | None
    created_at: float
    last_activity: float
    message_count: int
    status: SessionStatus
    attached_by: str | None = None


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------


class SessionManager:
    """Manages sessions in a SQLite WAL database."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,  # autocommit
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        logger.info("Session database opened at %s", self._db_path)

    def close(self) -> None:
        self._conn.close()

    def create_session(
        self,
        client_type: ClientType,
        client_metadata: dict | None = None,
    ) -> Session:
        """Create a new session and return it."""
        now = time.time()
        session = Session(
            id=str(uuid.uuid4()),
            client_type=client_type,
            client_metadata=client_metadata or {},
            claude_session_id=None,
            claude_pid=None,
            created_at=now,
            last_activity=now,
            message_count=0,
            status=SessionStatus.ACTIVE,
        )
        self._conn.execute(
            """INSERT INTO sessions
               (id, client_type, client_metadata, claude_session_id, claude_pid,
                created_at, last_activity, message_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.id,
                session.client_type.value,
                json.dumps(session.client_metadata),
                session.claude_session_id,
                session.claude_pid,
                session.created_at,
                session.last_activity,
                session.message_count,
                session.status.value,
            ),
        )
        logger.info("Created session %s (type=%s)", session.id[:8], session.client_type.value)
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    def get_active_sessions(self) -> list[Session]:
        """Get all active sessions."""
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE status = ?", (SessionStatus.ACTIVE.value,)
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def update_activity(self, session_id: str) -> None:
        """Update the last_activity timestamp for a session."""
        self._conn.execute(
            "UPDATE sessions SET last_activity = ? WHERE id = ?",
            (time.time(), session_id),
        )

    def increment_message_count(self, session_id: str) -> None:
        """Increment the message count for a session."""
        self._conn.execute(
            "UPDATE sessions SET message_count = message_count + 1, last_activity = ? WHERE id = ?",
            (time.time(), session_id),
        )

    def set_claude_info(
        self,
        session_id: str,
        claude_session_id: str | None = None,
        claude_pid: int | None = None,
    ) -> None:
        """Update the claude process info for a session."""
        self._conn.execute(
            "UPDATE sessions SET claude_session_id = ?, claude_pid = ? WHERE id = ?",
            (claude_session_id, claude_pid, session_id),
        )

    def set_status(self, session_id: str, status: SessionStatus) -> None:
        """Update session status."""
        self._conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?",
            (status.value, session_id),
        )

    def expire_idle_sessions(self, idle_timeout_seconds: int) -> list[Session]:
        """Mark sessions as idle if they haven't been used within the timeout.

        Returns the list of sessions that were marked idle.
        """
        cutoff = time.time() - idle_timeout_seconds
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE status = ? AND last_activity < ?",
            (SessionStatus.ACTIVE.value, cutoff),
        ).fetchall()

        sessions = [self._row_to_session(r) for r in rows]
        if sessions:
            ids = [s.id for s in sessions]
            placeholders = ",".join("?" for _ in ids)
            self._conn.execute(
                f"UPDATE sessions SET status = ? WHERE id IN ({placeholders})",
                [SessionStatus.IDLE.value] + ids,
            )
            logger.info("Expired %d idle sessions", len(sessions))
        return sessions

    def expire_old_sessions(self, expiry_seconds: int) -> list[Session]:
        """Mark sessions as expired if they are older than the expiry time.

        Returns the list of sessions that were marked expired.
        """
        cutoff = time.time() - expiry_seconds
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE status IN (?, ?) AND last_activity < ?",
            (SessionStatus.ACTIVE.value, SessionStatus.IDLE.value, cutoff),
        ).fetchall()

        sessions = [self._row_to_session(r) for r in rows]
        if sessions:
            ids = [s.id for s in sessions]
            placeholders = ",".join("?" for _ in ids)
            self._conn.execute(
                f"UPDATE sessions SET status = ? WHERE id IN ({placeholders})",
                [SessionStatus.EXPIRED.value] + ids,
            )
            logger.info("Expired %d old sessions", len(sessions))
        return sessions

    # -----------------------------------------------------------------------
    # Message history
    # -----------------------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source: str | None = None,
    ) -> None:
        """Record a message in the session history."""
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, source, timestamp) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, source, time.time()),
        )

    def get_messages(
        self,
        session_id: str,
        since: float | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get message history for a session.

        Args:
            session_id: The session to query.
            since: Only return messages after this timestamp.
            limit: Maximum number of messages to return.
        """
        if since is not None:
            rows = self._conn.execute(
                "SELECT role, content, source, timestamp FROM messages "
                "WHERE session_id = ? AND timestamp > ? ORDER BY id LIMIT ?",
                (session_id, since, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT role, content, source, timestamp FROM messages "
                "WHERE session_id = ? ORDER BY id LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "source": r["source"], "timestamp": r["timestamp"]}
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # TUI attach/detach
    # -----------------------------------------------------------------------

    def attach_session(self, session_id: str, client_id: str) -> None:
        """Mark a session as attached by a TUI client."""
        self._conn.execute(
            "UPDATE sessions SET attached_by = ?, last_activity = ? WHERE id = ?",
            (client_id, time.time(), session_id),
        )
        logger.info("Session %s attached by client %s", session_id[:8], client_id[:8])

    def detach_session(self, session_id: str, claude_session_id: str | None = None) -> None:
        """Release a session from TUI attachment, optionally updating claude_session_id."""
        if claude_session_id:
            self._conn.execute(
                "UPDATE sessions SET attached_by = NULL, claude_session_id = ?, last_activity = ? WHERE id = ?",
                (claude_session_id, time.time(), session_id),
            )
        else:
            self._conn.execute(
                "UPDATE sessions SET attached_by = NULL, last_activity = ? WHERE id = ?",
                (time.time(), session_id),
            )
        logger.info("Session %s detached", session_id[:8])

    def detach_by_client(self, client_id: str) -> int:
        """Detach all sessions attached by a given client. Returns count detached."""
        now = time.time()
        cursor = self._conn.execute(
            "UPDATE sessions SET attached_by = NULL, last_activity = ? WHERE attached_by = ?",
            (now, client_id),
        )
        count = cursor.rowcount
        if count:
            logger.info("Detached %d sessions from client %s", count, client_id[:8])
        return count

    def get_listable_sessions(self) -> list[Session]:
        """Get all active/idle sessions suitable for TUI listing."""
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE status IN (?, ?) ORDER BY last_activity DESC",
            (SessionStatus.ACTIVE.value, SessionStatus.IDLE.value),
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _migrate(self) -> None:
        """Run schema migrations for columns added after initial release."""
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "attached_by" not in columns:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN attached_by TEXT")
            logger.info("Migrated sessions table: added attached_by column")

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            client_type=ClientType(row["client_type"]),
            client_metadata=json.loads(row["client_metadata"]) if row["client_metadata"] else {},
            claude_session_id=row["claude_session_id"],
            claude_pid=row["claude_pid"],
            created_at=row["created_at"],
            last_activity=row["last_activity"],
            message_count=row["message_count"],
            status=SessionStatus(row["status"]),
            attached_by=row["attached_by"] if "attached_by" in row.keys() else None,
        )
