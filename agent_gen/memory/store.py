"""Episodic + conversation memory backed by SQLite (stdlib)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Memory:
    """Append-only episodic log + persistent conversation transcript."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    session TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                );
                """
            )

    # -- episodic log ----------------------------------------------------- #
    def log(self, kind: str, payload: Dict[str, Any] | None = None) -> int:
        payload = payload or {}
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO episodes (ts, kind, payload) VALUES (?, ?, ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), kind, json.dumps(payload)),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, kind, payload FROM episodes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except json.JSONDecodeError:
                payload = {"raw": r["payload"]}
            out.append({"ts": r["ts"], "kind": r["kind"], "payload": payload})
        return out

    # -- conversation ----------------------------------------------------- #
    def add_message(self, session: str, role: str, content: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO conversations (ts, session, role, content) VALUES (?, ?, ?, ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), session, role, content),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def history(self, session: str, limit: int = 500) -> List[Tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM conversations WHERE session = ? ORDER BY id ASC LIMIT ?",
                (session, limit),
            ).fetchall()
        return [(r["role"], r["content"]) for r in rows]

    def sessions(self) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT session FROM conversations ORDER BY session"
            ).fetchall()
        return [r["session"] for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
