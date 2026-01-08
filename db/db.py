from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# resolve repo root
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "demo.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_db_initialized() -> None:
    """
    Initialize schema if needed.
    IMPORTANT: Do NOT call connect() here (would recurse).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect():
    ensure_db_initialized()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(query: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def fetch_one(query: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def execute(query: str, params: Tuple[Any, ...] = ()) -> int:
    with connect() as conn:
        cur = conn.execute(query, params)
        conn.commit()
        return int(cur.lastrowid)


def executemany(query: str, rows: Iterable[Tuple[Any, ...]]) -> None:
    with connect() as conn:
        conn.executemany(query, rows)
        conn.commit()


def insert_audit_event(
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> int:
    return execute(
        """
        INSERT INTO audit_events(entity_type, entity_id, action, before_json, after_json, actor, created_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            entity_type,
            entity_id,
            action,
            json.dumps(before) if before is not None else None,
            json.dumps(after) if after is not None else None,
            actor,
            utc_now_iso(),
        ),
    )
