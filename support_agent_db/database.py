from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "support_agent.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class Database:
    """Многопоточный SQLite-слой без внешних ORM-зависимостей.

    Использует thread-local соединения для безопасной работы в мультисессионном
    многопоточном окружении.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    @property
    def connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.connection = conn
        return self._local.connection

    def initialize(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        self.connection.executescript(schema)
        self.connection.commit()

    def close(self) -> None:
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None

    def __enter__(self) -> "Database":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc:
            self.connection.rollback()
        self.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, params)

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]

    def create_conversation(
        self,
        user_id: int,
        channel: str = "cli",
        external_id: str | None = None,
    ) -> int:
        cursor = self.execute(
            """
            INSERT INTO conversations(user_id, channel, external_id)
            VALUES (?, ?, ?)
            """,
            (user_id, channel, external_id),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def get_conversation_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        )

    def create_user(
        self,
        name: str,
        external_id: str | None = None,
        email: str | None = None,
        department: str | None = None,
        role: str = "user",
    ) -> int:
        cursor = self.execute(
            """
            INSERT INTO users(external_id, name, email, department, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (external_id, name, email, department, role),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_request(
        self,
        user_id: int,
        question: str,
        conversation_id: int | None = None,
        channel: str = "cli",
        category: str | None = None,
    ) -> int:
        cursor = self.execute(
            """
            INSERT INTO requests(user_id, conversation_id, channel, category, question)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, conversation_id, channel, category, question),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def complete_request(
        self,
        request_id: int,
        answer: str,
        status: str = "success",
        confidence: float | None = None,
        response_time_ms: int | None = None,
        was_escalated: bool = False,
        error_message: str | None = None,
        category: str | None = None,
    ) -> None:
        self.execute(
            """
            UPDATE requests
            SET answer = ?, status = ?, confidence = ?, response_time_ms = ?,
                was_escalated = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP,
                category = COALESCE(?, category)
            WHERE id = ?
            """,
            (
                answer,
                status,
                confidence,
                response_time_ms,
                int(was_escalated),
                error_message,
                category,
                request_id,
            ),
        )
        self.connection.commit()

    def add_message(
        self,
        conversation_id: int,
        sender_type: str,
        message: str,
        request_id: int | None = None,
    ) -> int:
        cursor = self.execute(
            """
            INSERT INTO messages(conversation_id, request_id, sender_type, message)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, request_id, sender_type, message),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_escalation(
        self,
        request_id: int,
        reason: str,
        confidence: float | None = None,
    ) -> int:
        cursor = self.execute(
            """
            INSERT INTO escalations(request_id, reason, confidence)
            VALUES (?, ?, ?)
            """,
            (request_id, reason, confidence),
        )
        self.execute(
            "UPDATE requests SET was_escalated = 1, status = 'escalated' WHERE id = ?",
            (request_id,),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_feedback(self, request_id: int, rating: int, comment: str | None = None) -> int:
        cursor = self.execute(
            """
            INSERT INTO feedback(request_id, rating, comment)
            VALUES (?, ?, ?)
            """,
            (request_id, rating, comment),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_skill(
        self,
        name: str,
        slug: str,
        description: str | None,
        category: str | None,
        source_repo: str,
        source_url: str,
        skill_type: str = "reference",
        execution_mode: str = "external",
        local_path: str | None = None,
        version: str | None = None,
    ) -> int:
        cursor = self.execute(
            """
            INSERT INTO skills(
                name, slug, description, category, source_repo, source_url,
                skill_type, execution_mode, local_path, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                category = excluded.category,
                source_repo = excluded.source_repo,
                source_url = excluded.source_url,
                skill_type = excluded.skill_type,
                execution_mode = excluded.execution_mode,
                local_path = excluded.local_path,
                version = excluded.version,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                name,
                slug,
                description,
                category,
                source_repo,
                source_url,
                skill_type,
                execution_mode,
                local_path,
                version,
            ),
        )
        self.connection.commit()
        row = self.fetch_one("SELECT id FROM skills WHERE slug = ?", (slug,))
        return int(row["id"])

    def dashboard_summary(self) -> dict[str, Any]:
        return self.fetch_one("SELECT * FROM v_dashboard_summary") or {}

    def daily_stats(self) -> list[dict[str, Any]]:
        return self.fetch_all("SELECT * FROM v_daily_stats")

    def category_stats(self) -> list[dict[str, Any]]:
        return self.fetch_all("SELECT * FROM v_category_stats")

    def active_skills(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM skills WHERE is_active = 1 ORDER BY category, name"
        )

    def get_setting(self, key: str) -> str | None:
        row = self.fetch_one("SELECT value FROM agent_settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str, description: str | None = None) -> None:
        self.execute(
            """
            INSERT INTO agent_settings(key, value, description)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                description = COALESCE(excluded.description, agent_settings.description),
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value, description),
        )
        self.connection.commit()
