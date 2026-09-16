"""Durable SQLite task store and bounded in-process Agent runner."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.agent import config
from app.agent.graphs.advisor import build_advisor_graph
from app.agent.prompts import PROMPTS_VERSION

_SCHEMA_VERSION = 1
_GRAPH_VERSION = "2026-09-16.1"
_TOOLSET_VERSION = "2026-09-16.1"
_TERMINAL = {"ready", "failed", "timeout", "cancelled"}
_tasks: set[asyncio.Task] = set()
_semaphore: asyncio.Semaphore | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','ready','failed','timeout','cancelled')),
    mode TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT,
    error_code TEXT,
    error_message TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    token_total INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    graph_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    prompt_version TEXT NOT NULL,
    toolset_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_user_status ON agent_jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_created ON agent_jobs(created_at);
CREATE TABLE IF NOT EXISTS agent_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES agent_jobs(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_events_job_seq ON agent_events(job_id, seq);
CREATE TABLE IF NOT EXISTS agent_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES agent_jobs(id) ON DELETE CASCADE,
    node TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_feedback (
    job_id TEXT PRIMARY KEY REFERENCES agent_jobs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    helpful INTEGER NOT NULL CHECK (helpful IN (0,1)),
    reason TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.AGENT_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        now = _now()
        stale = conn.execute("SELECT id FROM agent_jobs WHERE status IN ('pending','running')").fetchall()
        conn.execute(
            "UPDATE agent_jobs SET status='failed', error_code='restart', "
            "error_message='服务重启，任务已终止', finished_at=? WHERE status IN ('pending','running')",
            (now,),
        )
        for row in stale:
            conn.execute(
                "INSERT INTO agent_events(job_id,type,message,created_at) VALUES (?,?,?,?)",
                (row["id"], "failed", "服务重启，任务已终止", now),
            )
        conn.execute(
            "DELETE FROM agent_jobs WHERE created_at < datetime('now', ?)",
            (f"-{config.AGENT_JOB_RETENTION_HOURS} hours",),
        )
        conn.execute(
            "DELETE FROM agent_traces WHERE created_at < datetime('now', ?)",
            (f"-{config.AGENT_TRACE_RETENTION_DAYS} days",),
        )


def is_allowed(user: Any) -> bool:
    if not config.AGENT_ALLOWLIST:
        return False
    candidates = {
        str(user["id"]).lower(), str(user["email"]).lower(), str(user["username"]).lower()
    }
    return bool(candidates & config.AGENT_ALLOWLIST)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _find_active(user_id: int):
    with _connect() as conn:
        return _row(conn.execute(
            "SELECT * FROM agent_jobs WHERE user_id=? AND status IN ('pending','running') ORDER BY created_at LIMIT 1",
            (user_id,),
        ).fetchone())


def _hourly_count(user_id: int) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) n FROM agent_jobs WHERE user_id=? AND created_at >= datetime('now','-1 hour')",
            (user_id,),
        ).fetchone()["n"]


def _daily_tokens() -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COALESCE(SUM(token_total),0) n FROM agent_jobs WHERE created_at >= datetime('now','start of day')",
        ).fetchone()["n"]


async def admission(user_id: int) -> tuple[str, dict[str, Any] | None]:
    active, count, tokens = await asyncio.gather(
        run_in_threadpool(_find_active, user_id),
        run_in_threadpool(_hourly_count, user_id),
        run_in_threadpool(_daily_tokens),
    )
    if active:
        return "active", active
    if count >= config.AGENT_USER_HOURLY_LIMIT:
        return "rate_limit", None
    if config.AGENT_DAILY_TOKEN_BUDGET and tokens >= config.AGENT_DAILY_TOKEN_BUDGET:
        return "budget", None
    return "ok", None


def _create(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    now = _now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO agent_jobs(
                id,user_id,status,mode,request_json,graph_version,schema_version,
                prompt_version,toolset_version,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (job_id, user_id, "pending", payload["mode"], json.dumps(payload, ensure_ascii=False),
             _GRAPH_VERSION, _SCHEMA_VERSION, PROMPTS_VERSION, _TOOLSET_VERSION, now),
        )
        conn.execute(
            "INSERT INTO agent_events(job_id,type,message,created_at) VALUES (?,?,?,?)",
            (job_id, "queued", "任务已进入队列", now),
        )
    return {"id": job_id, "status": "pending"}


async def create(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    job = await run_in_threadpool(_create, user_id, payload)
    task = asyncio.create_task(_run(job["id"], payload))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


def _append_event(job_id: str, event_type: str, message: str):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO agent_events(job_id,type,message,created_at) VALUES (?,?,?,?)",
            (job_id, event_type, message, _now()),
        )


def _set_running(job_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE agent_jobs SET status='running', started_at=? "
            "WHERE id=? AND status='pending' AND cancel_requested=0",
            (_now(), job_id),
        )
        return cur.rowcount == 1


def _finish(job_id: str, status: str, *, result=None, error_code=None, error_message=None,
            token_total=0, duration_ms=None):
    with _connect() as conn:
        conn.execute(
            """UPDATE agent_jobs SET status=?, result_json=?, error_code=?, error_message=?,
               token_total=?, duration_ms=?, finished_at=? WHERE id=?""",
            (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
             error_code, error_message, token_total, duration_ms, _now(), job_id),
        )


def _cancel_requested(job_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT cancel_requested FROM agent_jobs WHERE id=?", (job_id,)).fetchone()
        return bool(row and row["cancel_requested"])


def _serialize_evidence(state: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = state.get("ledger")
    if ledger is None:
        return []
    return [
        {"eid": ev.eid, "tool": ev.tool, "args": ev.args, "data": ev.data, "ts": ev.ts}
        for ev in ledger.all()
    ]


async def _run(job_id: str, payload: dict[str, Any]) -> None:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(config.AGENT_MAX_CONCURRENCY)
    started = time.monotonic()
    try:
        async with _semaphore:
            if not await run_in_threadpool(_set_running, job_id):
                return
            await run_in_threadpool(_append_event, job_id, "running", "参谋正在查资料")
            state = {
                "job_id": job_id,
                "question": payload["message"],
                "mode": payload["mode"],
                "profile": payload.get("profile") or {},
                "page_context": payload.get("page_context") or {},
                "history": payload.get("history") or [],
            }
            graph = build_advisor_graph()
            out = await asyncio.wait_for(
                graph.ainvoke(state), timeout=config.AGENT_JOB_TIMEOUT_SECONDS
            )
            if await run_in_threadpool(_cancel_requested, job_id):
                await run_in_threadpool(_finish, job_id, "cancelled", error_code="cancelled",
                                        error_message="任务已取消",
                                        duration_ms=int((time.monotonic() - started) * 1000))
                await run_in_threadpool(_append_event, job_id, "cancelled", "任务已取消")
                return
            usage = out.get("usage") or {}
            token_total = int(usage.get("total_tokens") or usage.get("tokens") or 0)
            result = {
                "answer": out.get("answer"), "clarify": out.get("clarify"),
                "evidence": _serialize_evidence(out),
            }
            await run_in_threadpool(_finish, job_id, "ready", result=result,
                                    token_total=token_total,
                                    duration_ms=int((time.monotonic() - started) * 1000))
            await run_in_threadpool(_append_event, job_id, "ready", "分析完成")
    except asyncio.TimeoutError:
        await run_in_threadpool(_finish, job_id, "timeout", error_code="timeout",
                                error_message="分析超时，请缩小问题范围后重试",
                                duration_ms=int((time.monotonic() - started) * 1000))
        await run_in_threadpool(_append_event, job_id, "timeout", "分析超时")
    except Exception:  # noqa: BLE001 - only sanitized error reaches persistent user-visible state
        await run_in_threadpool(_finish, job_id, "failed", error_code="internal_error",
                                error_message="参谋服务暂时不可用，请稍后重试",
                                duration_ms=int((time.monotonic() - started) * 1000))
        await run_in_threadpool(_append_event, job_id, "failed", "参谋服务暂时不可用")


def _get(job_id: str, user_id: int, after: int):
    with _connect() as conn:
        job = conn.execute(
            "SELECT * FROM agent_jobs WHERE id=? AND user_id=?", (job_id, user_id)
        ).fetchone()
        if not job:
            return None
        events = [dict(row) for row in conn.execute(
            "SELECT seq,type,message,created_at FROM agent_events WHERE job_id=? AND seq>? ORDER BY seq",
            (job_id, after),
        )]
        result = json.loads(job["result_json"]) if job["result_json"] else None
        return {
            "job_id": job["id"], "status": job["status"], "events": events,
            "result": result, "error_code": job["error_code"],
            "error_message": job["error_message"], "created_at": job["created_at"],
            "finished_at": job["finished_at"],
        }


async def get(job_id: str, user_id: int, after: int = 0):
    return await run_in_threadpool(_get, job_id, user_id, after)


def _cancel(job_id: str, user_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM agent_jobs WHERE id=? AND user_id=?", (job_id, user_id)
        ).fetchone()
        if not row:
            return None
        if row["status"] in _TERMINAL:
            return row["status"]
        conn.execute("UPDATE agent_jobs SET cancel_requested=1 WHERE id=?", (job_id,))
        if row["status"] == "pending":
            conn.execute(
                "UPDATE agent_jobs SET status='cancelled', error_code='cancelled', "
                "error_message='任务已取消', finished_at=? WHERE id=?",
                (_now(), job_id),
            )
            conn.execute(
                "INSERT INTO agent_events(job_id,type,message,created_at) VALUES (?,?,?,?)",
                (job_id, "cancelled", "任务已取消", _now()),
            )
            return "cancelled"
        return "cancelling"


async def cancel(job_id: str, user_id: int):
    return await run_in_threadpool(_cancel, job_id, user_id)


def _feedback(job_id: str, user_id: int, helpful: bool, reason: str | None):
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM agent_jobs WHERE id=? AND user_id=?", (job_id, user_id)
        ).fetchone()
        if not exists:
            return False
        conn.execute(
            """INSERT INTO agent_feedback(job_id,user_id,helpful,reason,created_at)
               VALUES (?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET
               helpful=excluded.helpful, reason=excluded.reason, created_at=excluded.created_at""",
            (job_id, user_id, int(helpful), reason, _now()),
        )
        return True


async def feedback(job_id: str, user_id: int, helpful: bool, reason: str | None):
    return await run_in_threadpool(_feedback, job_id, user_id, helpful, reason)
