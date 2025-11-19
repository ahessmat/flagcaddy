from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


def utcnow() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                raw_input TEXT,
                raw_output TEXT,
                fingerprint TEXT,
                novelty REAL,
                duplicate INTEGER DEFAULT 0,
                started_at TEXT,
                finished_at TEXT,
                llm_status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                fact_type TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(session_id, fact_type, fact_value),
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                event_ids TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )
        self.conn.commit()

    def get_session_id(self, name: str) -> Optional[int]:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM sessions WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return int(row["id"])
        return None

    def ensure_session(self, name: str) -> int:
        existing = self.get_session_id(name)
        if existing:
            return existing
        now = utcnow()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO sessions (name, created_at) VALUES (?, ?)",
            (name, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_sessions(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, name, created_at FROM sessions ORDER BY created_at DESC"
        )
        return cur.fetchall()

    def insert_event(
        self,
        session_id: int,
        *,
        command: str,
        raw_input: str,
        raw_output: str,
        fingerprint: str,
        novelty: float,
        duplicate: bool,
        started_at: Optional[str],
        finished_at: Optional[str],
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO events (
                session_id,
                command,
                raw_input,
                raw_output,
                fingerprint,
                novelty,
                duplicate,
                started_at,
                finished_at,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                command,
                raw_input,
                raw_output,
                fingerprint,
                novelty,
                1 if duplicate else 0,
                started_at,
                finished_at,
                utcnow(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def find_event_by_fingerprint(
        self, session_id: int, fingerprint: str
    ) -> Optional[int]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id FROM events WHERE session_id = ? AND fingerprint = ?",
            (session_id, fingerprint),
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None

    def add_fact(self, session_id: int, fact_type: str, fact_value: str) -> bool:
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO facts (session_id, fact_type, fact_value, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, fact_type, fact_value, utcnow()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def list_facts(self, session_id: int, fact_type: Optional[str] = None) -> List[str]:
        cur = self.conn.cursor()
        if fact_type:
            cur.execute(
                "SELECT fact_value FROM facts WHERE session_id=? AND fact_type=?",
                (session_id, fact_type),
            )
        else:
            cur.execute(
                "SELECT fact_value FROM facts WHERE session_id=?",
                (session_id,),
            )
        return [row["fact_value"] for row in cur.fetchall()]

    def last_llm_timestamp(self, session_id: int) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT created_at FROM recommendations
            WHERE session_id=? AND source='llm'
            ORDER BY created_at DESC LIMIT 1
            """,
            (session_id,),
        )
        row = cur.fetchone()
        return row["created_at"] if row else None

    def recent_events(self, session_id: int, limit: int = 10) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, command, raw_output, novelty, duplicate, created_at
            FROM events
            WHERE session_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        return cur.fetchall()

    def add_recommendation(
        self,
        session_id: int,
        *,
        source: str,
        title: str,
        body: str,
        event_ids: Optional[Sequence[int]] = None,
    ) -> int:
        payload = json.dumps(list(event_ids) if event_ids else [])
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO recommendations (
                session_id, source, title, body, event_ids, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, source, title, body, payload, utcnow()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_recommendations(
        self, session_id: int, limit: int = 20
    ) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, source, title, body, created_at
            FROM recommendations
            WHERE session_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        return cur.fetchall()


__all__ = ["Database"]
