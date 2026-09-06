from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class ScoreCache:
    """SQLite TTL cache for Activate score payloads."""

    def __init__(self, db_path: Path, ttl_seconds: int = 600) -> None:
        self.db_path = Path(db_path)
        self.ttl_seconds = ttl_seconds
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at REAL NOT NULL
                )
                """
            )

    def get(self, key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload, fetched_at FROM cache_entries WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        payload, fetched_at = row
        if time.time() - float(fetched_at) > self.ttl_seconds:
            return None
        return json.loads(payload)

    def get_stale(self, key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload FROM cache_entries WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def set(self, key: str, payload: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO cache_entries(cache_key, payload, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                  payload=excluded.payload,
                  fetched_at=excluded.fetched_at
                """,
                (key, json.dumps(payload), time.time()),
            )

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM cache_entries")
