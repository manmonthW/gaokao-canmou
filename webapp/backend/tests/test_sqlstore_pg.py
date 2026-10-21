"""PostgreSQL 模式集成测试（用户库 + Agent 任务库）。

仅在设置 TEST_APP_DB_URL 时运行，例如：
    TEST_APP_DB_URL=postgresql://app:app@127.0.0.1:55432/appdb pytest tests/test_sqlstore_pg.py
每个用例前清空相关表，请勿指向有数据的库。
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

from app import sqlstore, user_db
from app.agent import jobs

PG_URL = os.environ.get("TEST_APP_DB_URL", "").strip()
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_APP_DB_URL 未设置")

_TABLES = "agent_feedback, agent_traces, agent_events, agent_jobs, outcome_feedback, user_data, users"


@pytest.fixture(autouse=True)
def pg_store(monkeypatch):
    monkeypatch.setattr(sqlstore, "APP_DB_URL", PG_URL)
    monkeypatch.setattr(sqlstore, "IS_PG", True)
    monkeypatch.setattr(sqlstore, "_pg_pool", None)
    monkeypatch.setattr(user_db, "_initialized", False)
    monkeypatch.setattr(jobs, "_initialized_for", None)
    monkeypatch.setattr(jobs.config, "AGENT_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(jobs.config, "AGENT_JOB_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(jobs.config, "AGENT_USER_HOURLY_LIMIT", 30)
    monkeypatch.setattr(jobs.config, "AGENT_DAILY_TOKEN_BUDGET", 1000)
    jobs._semaphore = None
    jobs._tasks.clear()
    user_db.init_db()
    jobs.init_db()
    with sqlstore.connect("") as conn:
        conn.execute(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE")
    yield
    if sqlstore._pg_pool is not None:
        sqlstore._pg_pool.closeall()


# ---------------- 用户库 ----------------

def test_register_login_and_case_insensitive_uniqueness():
    uid = asyncio.run(user_db.create_user("a@x.com", "Alice", "hash"))
    assert isinstance(uid, int)
    assert asyncio.run(user_db.email_exists("A@X.COM"))
    assert asyncio.run(user_db.username_exists("alice"))

    user = asyncio.run(user_db.get_user_by_login("ALICE"))
    assert user["id"] == uid and user["email"] == "a@x.com"
    assert user["created_at"] and user["last_login_at"] is None

    asyncio.run(user_db.touch_login(uid))
    assert asyncio.run(user_db.get_user_by_id(uid))["last_login_at"]

    # 路由层依赖 create_user 在并发重复时抛异常（409 兜底）
    with pytest.raises(Exception):
        asyncio.run(user_db.create_user("A@x.com", "bob", "hash"))
    # 失败事务已回滚，连接可继续用（PG 序列不回滚，id 不保证连续）
    assert asyncio.run(user_db.create_user("b@x.com", "bob", "hash")) > uid


def test_user_data_roundtrip_and_upsert():
    uid = asyncio.run(user_db.create_user("c@x.com", "carol", "hash"))
    assert asyncio.run(user_db.get_data(uid)) == "{}"
    asyncio.run(user_db.set_data(uid, '{"favs": [1]}'))
    asyncio.run(user_db.set_data(uid, '{"favs": [1, 2]}'))
    assert asyncio.run(user_db.get_data(uid)) == '{"favs": [1, 2]}'
    assert asyncio.run(user_db.get_data(9999)) == "{}"


def test_outcome_feedback_and_summary():
    uid = asyncio.run(user_db.create_user("d@x.com", "dave", "hash"))
    base = {"examinee_year": 2026, "outcome": "admitted", "admitted_risk": "稳"}
    fid = asyncio.run(user_db.add_feedback({**base, "user_id": uid}))
    asyncio.run(user_db.add_feedback({**base, "admitted_risk": "保"}))  # 匿名
    asyncio.run(user_db.add_feedback({"examinee_year": 2026, "outcome": "slipped"}))
    assert isinstance(fid, int)
    summary = asyncio.run(user_db.feedback_summary())
    assert summary == {
        "total": 3,
        "by_outcome": {"admitted": 2, "slipped": 1},
        "by_admitted_risk": {"稳": 1, "保": 1},
    }


def test_schema_init_is_idempotent():
    user_db._initialized = False
    user_db.init_db()
    jobs.init_db()
    jobs.init_db()


# ---------------- Agent 任务库 ----------------

def test_job_lifecycle_events_and_owner_isolation(monkeypatch):
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
    assert [e["type"] for e in result["events"]] == ["queued", "running", "ready"]
    assert asyncio.run(jobs.get(job["id"], 2)) is None
    after = result["events"][0]["seq"]
    assert asyncio.run(jobs.get(job["id"], 1, after=after))["events"][0]["type"] == "running"
    assert jobs._daily_tokens() == 12
    assert asyncio.run(jobs.admission(1))[0] == "ok"


def test_admission_active_conflict_and_budget():
    payload = {"mode": "问答", "message": "推荐沈阳的学校"}
    active = jobs._create(1, payload)
    decision, row = asyncio.run(jobs.admission(1, payload))
    assert (decision, row["id"]) == ("active", active["id"])
    decision, _ = asyncio.run(jobs.admission(1, {**payload, "message": "大连"}))
    assert decision == "conflict"

    jobs._finish(active["id"], "ready", token_total=1000)
    assert asyncio.run(jobs.admission(2))[0] == "budget"


def test_cancel_and_feedback_upsert():
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert asyncio.run(jobs.cancel(job["id"], 2)) is None
    assert asyncio.run(jobs.cancel(job["id"], 1)) == "cancelled"
    assert asyncio.run(jobs.cancel(job["id"], 1)) == "cancelled"  # 终态再取消
    assert asyncio.run(jobs.feedback(job["id"], 1, True, "有帮助")) is True
    assert asyncio.run(jobs.feedback(job["id"], 1, False, "改主意")) is True
    assert asyncio.run(jobs.feedback(job["id"], 2, False, None)) is False
    with sqlstore.connect("") as conn:
        row = conn.execute("SELECT helpful, reason FROM agent_feedback WHERE job_id=?", (job["id"],)).fetchone()
    assert (row["helpful"], row["reason"]) == (0, "改主意")


def test_terminal_state_and_stale_job_expiry():
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert jobs._finish(job["id"], "timeout", error_code="timeout") is True
    assert jobs._finish(job["id"], "ready", result={"answer": "late"}) is False

    stale_job = jobs._create(2, {"mode": "问答", "message": "test"})
    stale = (datetime.now(timezone.utc) - timedelta(seconds=40)).strftime("%Y-%m-%d %H:%M:%S.%f")
    with sqlstore.connect("") as conn:
        conn.execute("UPDATE agent_jobs SET created_at=? WHERE id=?", (stale, stale_job["id"]))
    result = asyncio.run(jobs.get(stale_job["id"], 2))
    assert result["status"] == "timeout"
    assert result["events"][-1]["type"] == "timeout"


def test_reinit_does_not_fail_running_jobs_in_pg():
    """PG 共享库下，重新建表不能把其他实例上正在跑的任务标成失败。"""
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert jobs._set_running(job["id"])
    jobs.init_db()
    assert asyncio.run(jobs.get(job["id"], 1))["status"] == "running"


def test_concurrent_cold_start_schema_init():
    """多个线程同时首次建表（模拟多实例冷启动）不报错。"""
    import threading

    with sqlstore.connect("") as conn:
        conn.execute(f"DROP TABLE IF EXISTS {_TABLES} CASCADE")
    errors = []

    def boot():
        try:
            with sqlstore.connect("") as conn:
                sqlstore.schema_lock(conn, 7301)
                conn.executescript(user_db._PG_SCHEMA)
            jobs._init_db()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=boot) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


# ---------------- 连接池 ----------------

def test_pool_queues_instead_of_failing_when_exhausted():
    import threading
    import time

    p = sqlstore.make_blocking_pool(2, PG_URL)
    results, errors = [], []

    def work():
        try:
            conn = p.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_sleep(0.2)")
                conn.rollback()
                results.append(1)
            finally:
                p.putconn(conn)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    started = time.monotonic()
    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    p.closeall()
    assert errors == [] and len(results) == 6
    assert time.monotonic() - started >= 0.55  # 6 个任务 / 2 个连接 ≈ 3 轮


def test_pool_replaces_connection_killed_by_server(monkeypatch):
    monkeypatch.setattr(sqlstore, "_IDLE_CHECK_SECONDS", 0)
    p = sqlstore.make_blocking_pool(1, PG_URL)
    conn = p.getconn()
    with conn.cursor() as cur:
        cur.execute("SELECT pg_backend_pid()")
        pid = cur.fetchone()[0]
    conn.rollback()
    p.putconn(conn)

    # 模拟 Neon 空闲挂起 / 服务端断开
    admin = sqlstore.make_blocking_pool(1, PG_URL)
    c2 = admin.getconn()
    with c2.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
    c2.commit()
    admin.putconn(c2)
    admin.closeall()

    conn = p.getconn()
    with conn.cursor() as cur:
        cur.execute("SELECT pg_backend_pid()")
        assert cur.fetchone()[0] != pid
    conn.rollback()
    p.putconn(conn)
    p.closeall()


# ---------------- 跨实例限流 ----------------

def test_rate_limit_shared_across_instances(monkeypatch):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app import rate_limit

    monkeypatch.setattr(rate_limit, "_pg_ready", False)
    with sqlstore.connect("") as conn:
        conn.execute("DROP TABLE IF EXISTS rate_limit_hits")

    def req(ip):
        return SimpleNamespace(headers={"x-forwarded-for": f"{ip}, 10.0.0.1"}, client=None)

    # 两个 limiter 对象模拟两个 Serverless 实例，计数必须共享
    a = rate_limit.SlidingWindowLimiter(limit=3, window_seconds=60, name="t")
    b = rate_limit.SlidingWindowLimiter(limit=3, window_seconds=60, name="t")
    asyncio.run(a.check(req("1.1.1.1")))
    asyncio.run(b.check(req("1.1.1.1")))
    asyncio.run(a.check(req("1.1.1.1")))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(b.check(req("1.1.1.1")))
    assert exc.value.status_code == 429
    asyncio.run(b.check(req("2.2.2.2")))  # 其他 IP 不受影响
