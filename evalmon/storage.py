import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DB_PATH: Path | None = None


def get_db_path() -> Path:
    if _DB_PATH is not None:
        return _DB_PATH
    env = os.environ.get("EVALMON_DB_PATH")
    return Path(env) if env else Path.home() / ".evalmon/evalmon.db"


def set_db_path(path: str | Path | None) -> None:
    global _DB_PATH
    _DB_PATH = Path(path) if path is not None else None


def _conn() -> sqlite3.Connection:
    db = get_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS calls (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                provider      TEXT    NOT NULL,
                model         TEXT    NOT NULL,
                messages      TEXT    NOT NULL,
                response      TEXT    NOT NULL,
                input_tokens  INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd      REAL    DEFAULT 0.0,
                latency_ms    REAL    DEFAULT 0.0,
                prompt_version TEXT,
                user_id       TEXT,
                session_id    TEXT,
                tags          TEXT
            );

            CREATE TABLE IF NOT EXISTS evals (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL UNIQUE,
                criterion  TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS eval_results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_id         INTEGER NOT NULL,
                call_id         INTEGER NOT NULL,
                passed          INTEGER NOT NULL,
                score           REAL,
                judge_reasoning TEXT,
                created_at      TEXT    NOT NULL,
                FOREIGN KEY (eval_id) REFERENCES evals(id),
                FOREIGN KEY (call_id) REFERENCES calls(id)
            );
        """)


def insert_call(
    provider: str,
    model: str,
    messages: list,
    response: Any,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    prompt_version: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> int:
    init_db()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO calls
               (timestamp, provider, model, messages, response,
                input_tokens, output_tokens, cost_usd, latency_ms,
                prompt_version, user_id, session_id, tags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                provider, model,
                json.dumps(messages),
                json.dumps(response),
                input_tokens, output_tokens,
                cost_usd, latency_ms,
                prompt_version, user_id, session_id,
                json.dumps(tags) if tags else None,
            ),
        )
        return cur.lastrowid


def get_calls(
    limit: int = 200,
    provider: str | None = None,
    model: str | None = None,
) -> list[dict]:
    init_db()
    query = "SELECT * FROM calls"
    params: list = []
    filters = []
    if provider:
        filters.append("provider = ?")
        params.append(provider)
    if model:
        filters.append("model LIKE ?")
        params.append(f"%{model}%")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    with _conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def insert_eval(name: str, criterion: str) -> int:
    init_db()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO evals (name, criterion, created_at) VALUES (?,?,?)",
            (name, criterion, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def get_evals() -> list[dict]:
    init_db()
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evals ORDER BY created_at DESC"
        ).fetchall()]


def delete_eval_by_name(name: str) -> bool:
    init_db()
    with _conn() as conn:
        return conn.execute("DELETE FROM evals WHERE name = ?", (name,)).rowcount > 0


def insert_eval_result(
    eval_id: int, call_id: int,
    passed: bool, score: float, reasoning: str,
) -> int:
    init_db()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO eval_results
               (eval_id, call_id, passed, score, judge_reasoning, created_at)
               VALUES (?,?,?,?,?,?)""",
            (eval_id, call_id, int(passed), score, reasoning,
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def get_eval_results(
    eval_id: int | None = None,
    limit: int = 500,
) -> list[dict]:
    init_db()
    query = """
        SELECT er.*, e.name AS eval_name, e.criterion,
               c.model, c.provider, c.timestamp AS call_timestamp
        FROM eval_results er
        JOIN evals e ON e.id = er.eval_id
        JOIN calls c ON c.id = er.call_id
    """
    params: list = []
    if eval_id:
        query += " WHERE er.eval_id = ?"
        params.append(eval_id)
    query += " ORDER BY er.created_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
