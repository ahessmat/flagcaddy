"""Database management for FlagCaddy."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from .config import DB_PATH


class Database:
    """Manages the SQLite database for terminal captures and analysis."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Commands table - stores all terminal commands
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    command TEXT NOT NULL,
                    working_dir TEXT NOT NULL,
                    output TEXT,
                    exit_code INTEGER,
                    session_id TEXT
                )
            """)

            # Entities table - stores discovered hosts, networks, services
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    metadata TEXT,
                    UNIQUE(type, value)
                )
            """)

            # Analysis table - stores LLM analysis results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    scope_id TEXT,
                    summary TEXT NOT NULL,
                    recommendations TEXT NOT NULL,
                    confidence REAL,
                    metadata TEXT
                )
            """)

            # Entity relationships
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_commands (
                    entity_id INTEGER NOT NULL,
                    command_id INTEGER NOT NULL,
                    relevance REAL,
                    FOREIGN KEY (entity_id) REFERENCES entities(id),
                    FOREIGN KEY (command_id) REFERENCES commands(id),
                    PRIMARY KEY (entity_id, command_id)
                )
            """)

            # Indices for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_scope ON analysis(scope, scope_id)")

    def add_command(self, command: str, working_dir: str, output: str = "",
                    exit_code: int = 0, session_id: str = "") -> int:
        """Add a command execution record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO commands (timestamp, command, working_dir, output, exit_code, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), command, working_dir, output, exit_code, session_id))
            return cursor.lastrowid

    def add_entity(self, entity_type: str, value: str, metadata: Dict[str, Any] = None) -> int:
        """Add or update a discovered entity (host, network, service, etc.)."""
        now = datetime.utcnow().isoformat()
        metadata_json = json.dumps(metadata) if metadata else "{}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO entities (type, value, first_seen, last_seen, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(type, value) DO UPDATE SET
                    last_seen = ?,
                    metadata = ?
            """, (entity_type, value, now, now, metadata_json, now, metadata_json))

            # Get the entity ID
            cursor.execute("SELECT id FROM entities WHERE type = ? AND value = ?", (entity_type, value))
            return cursor.fetchone()[0]

    def link_entity_command(self, entity_id: int, command_id: int, relevance: float = 1.0):
        """Link an entity to a command."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO entity_commands (entity_id, command_id, relevance)
                VALUES (?, ?, ?)
            """, (entity_id, command_id, relevance))

    def add_analysis(self, scope: str, summary: str, recommendations: List[str],
                     scope_id: str = None, confidence: float = 1.0,
                     metadata: Dict[str, Any] = None) -> int:
        """Add an analysis result."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analysis (timestamp, scope, scope_id, summary, recommendations, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), scope, scope_id, summary,
                  json.dumps(recommendations), confidence, json.dumps(metadata or {})))
            return cursor.lastrowid

    def get_recent_commands(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent commands."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM commands
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a specific type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM entities
                WHERE type = ?
                ORDER BY last_seen DESC
            """, (entity_type,))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                entity = dict(row)
                entity['metadata'] = json.loads(entity.get('metadata', '{}'))
                result.append(entity)
            return result

    def get_entity_commands(self, entity_id: int) -> List[Dict[str, Any]]:
        """Get all commands related to an entity."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, ec.relevance
                FROM commands c
                JOIN entity_commands ec ON c.id = ec.command_id
                WHERE ec.entity_id = ?
                ORDER BY c.timestamp DESC
            """, (entity_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_analysis(self, scope: str = None, scope_id: str = None,
                     limit: int = 10) -> List[Dict[str, Any]]:
        """Get analysis results."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if scope and scope_id:
                cursor.execute("""
                    SELECT * FROM analysis
                    WHERE scope = ? AND scope_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (scope, scope_id, limit))
            elif scope:
                cursor.execute("""
                    SELECT * FROM analysis
                    WHERE scope = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (scope, limit))
            else:
                cursor.execute("""
                    SELECT * FROM analysis
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                analysis = dict(row)
                analysis['recommendations'] = json.loads(analysis.get('recommendations', '[]'))
                analysis['metadata'] = json.loads(analysis.get('metadata', '{}'))
                result.append(analysis)
            return result

    def get_all_entities(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all entities organized by type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT type FROM entities")
            types = [row[0] for row in cursor.fetchall()]

            result = {}
            for entity_type in types:
                result[entity_type] = self.get_entities_by_type(entity_type)
            return result
