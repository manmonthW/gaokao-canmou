import asyncio
import sqlite3
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from app.agent import jobs


def _configure(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.config, "AGENT_DB_PATH", str(tmp_path / "agent.db"))
    monkeypatch.setattr(jobs.config, "AGENT_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(jobs.config, "AGENT_JOB_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(jobs.config, "AGENT_USER_HOURLY_LIMIT", 30)
    monkeypatch.setattr(jobs.config, "AGENT_DAILY_TOKEN_BUDGET", 1000)
    jobs._semaphore = None
    jobs._tasks.clear()
    jobs.init_db()


def test_init_marks_interrupted_jobs_failed(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert jobs._set_running(job["id"])
    jobs.init_db()
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "failed"
    assert result["error_code"] == "restart"


def test_init_migrates_existing_jobs_table(monkeypatch, tmp_path):
    db_path = tmp_path / "agent.db"
    monkeypatch.setattr(jobs.config, "AGENT_DB_PATH", str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE agent_jobs (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, status TEXT NOT NULL,
                mode TEXT NOT NULL, request_json TEXT NOT NULL, result_json TEXT,
                error_code TEXT, error_message TEXT, graph_version TEXT NOT NULL,
                schema_version INTEGER NOT NULL, prompt_version TEXT NOT NULL,
                toolset_version TEXT NOT NULL, token_total INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER, created_at TEXT NOT NULL, started_at TEXT,
                finished_at TEXT
            )"""
        )

    jobs.init_db()

    with jobs._connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(agent_jobs)")}
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(agent_jobs)")}
    assert "request_fingerprint" in columns
    assert "idx_agent_jobs_fingerprint" in indexes


def test_admission_enforces_active_hourly_and_budget(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    active = jobs._create(1, {"mode": "问答", "message": "test"})
    decision, row = asyncio.run(jobs.admission(1))
    assert decision == "active"
    assert row["id"] == active["id"]

    jobs._finish(active["id"], "ready", token_total=1000)
    decision, _ = asyncio.run(jobs.admission(2))
    assert decision == "budget"

    monkeypatch.setattr(jobs.config, "AGENT_DAILY_TOKEN_BUDGET", 0)
    monkeypatch.setattr(jobs.config, "AGENT_USER_HOURLY_LIMIT", 1)
    jobs._create(3, {"mode": "问答", "message": "test"})
    jobs._finish(jobs._find_active(3)["id"], "ready")
    decision, _ = asyncio.run(jobs.admission(3))
    assert decision == "rate_limit"


def test_run_persists_result_events_and_owner_isolation(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    class FakeGraph:
        async def ainvoke(self, state):
            return {"clarify": "请补充位次", "usage": {"total_tokens": 12}}

    monkeypatch.setattr(jobs, "build_advisor_graph", lambda: FakeGraph())

    async def scenario():
        job = await jobs.create(1, {"mode": "问答", "message": "推荐学校"})
        await asyncio.gather(*list(jobs._tasks.values()))
        return job

    job = asyncio.run(scenario())
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "ready"
    assert result["result"]["clarify"] == "请补充位次"
    assert [event["type"] for event in result["events"]] == ["queued", "running", "ready"]
    assert asyncio.run(jobs.get(job["id"], 2)) is None
    assert asyncio.run(jobs.get(job["id"], 1, after=result["events"][0]["seq"]))["events"][0]["type"] == "running"


def test_finish_serializes_decimal_result(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    jobs._finish(job["id"], "ready", result={"evidence": {"score": Decimal("612.5")}})
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["result"]["evidence"]["score"] == 612.5


def test_cancel_pending_and_feedback(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert asyncio.run(jobs.cancel(job["id"], 2)) is None
    assert asyncio.run(jobs.cancel(job["id"], 1)) == "cancelled"
    assert asyncio.run(jobs.feedback(job["id"], 1, True, "有帮助")) is True
    assert asyncio.run(jobs.feedback(job["id"], 2, False, None)) is False


def test_timeout_is_terminal(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(jobs.config, "AGENT_JOB_TIMEOUT_SECONDS", 0.01)

    class SlowGraph:
        async def ainvoke(self, state):
            await asyncio.sleep(0.1)

    monkeypatch.setattr(jobs, "build_advisor_graph", lambda: SlowGraph())

    async def scenario():
        job = await jobs.create(1, {"mode": "问答", "message": "test"})
        await asyncio.gather(*list(jobs._tasks.values()))
        return job

    job = asyncio.run(scenario())
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "timeout"
    assert result["error_code"] == "timeout"


def test_get_and_admission_expire_orphaned_jobs(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    stale = (datetime.now(timezone.utc) - timedelta(seconds=40)).strftime("%Y-%m-%d %H:%M:%S.%f")
    with jobs._connect() as conn:
        conn.execute("UPDATE agent_jobs SET created_at=? WHERE id=?", (stale, job["id"]))

    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "timeout"
    assert result["error_code"] == "timeout"
    assert result["events"][-1]["type"] == "timeout"

    replacement = jobs._create(2, {"mode": "问答", "message": "test"})
    with jobs._connect() as conn:
        conn.execute("UPDATE agent_jobs SET created_at=? WHERE id=?", (stale, replacement["id"]))
    decision, active = asyncio.run(jobs.admission(2))
    assert decision == "ok"
    assert active is None


def test_admission_reuses_only_identical_request(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    payload = {"mode": "问答", "message": "推荐沈阳的学校"}
    active = jobs._create(1, payload)

    decision, row = asyncio.run(jobs.admission(1, payload))
    assert decision == "active"
    assert row["id"] == active["id"]

    decision, row = asyncio.run(jobs.admission(1, {**payload, "message": "推荐大连的学校"}))
    assert decision == "conflict"
    assert row["id"] == active["id"]


def test_cancel_running_task_is_terminal(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    class SlowGraph:
        async def ainvoke(self, state):
            await asyncio.sleep(10)

    monkeypatch.setattr(jobs, "build_advisor_graph", lambda: SlowGraph())

    async def scenario():
        job = await jobs.create(1, {"mode": "问答", "message": "test"})
        for _ in range(20):
            current = await jobs.get(job["id"], 1)
            if current["status"] == "running":
                break
            await asyncio.sleep(0.01)
        assert await jobs.cancel(job["id"], 1) == "cancelled"
        await asyncio.gather(*list(jobs._tasks.values()), return_exceptions=True)
        return job

    job = asyncio.run(scenario())
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "cancelled"
    assert result["events"][-1]["type"] == "cancelled"


def test_terminal_state_cannot_be_overwritten(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert jobs._finish(job["id"], "timeout", error_code="timeout") is True
    assert jobs._finish(job["id"], "ready", result={"answer": "late"}) is False
    assert asyncio.run(jobs.get(job["id"], 1))["status"] == "timeout"
