import asyncio
from decimal import Decimal

from app.agent import jobs


def _configure(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.config, "AGENT_DB_PATH", str(tmp_path / "agent.db"))
    monkeypatch.setattr(jobs.config, "AGENT_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(jobs.config, "AGENT_JOB_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(jobs.config, "AGENT_USER_HOURLY_LIMIT", 30)
    monkeypatch.setattr(jobs.config, "AGENT_DAILY_TOKEN_BUDGET", 1000)
    jobs._semaphore = None
    jobs.init_db()


def test_init_marks_interrupted_jobs_failed(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    job = jobs._create(1, {"mode": "问答", "message": "test"})
    assert jobs._set_running(job["id"])
    jobs.init_db()
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "failed"
    assert result["error_code"] == "restart"


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
        await asyncio.gather(*list(jobs._tasks))
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
        await asyncio.gather(*list(jobs._tasks))
        return job

    job = asyncio.run(scenario())
    result = asyncio.run(jobs.get(job["id"], 1))
    assert result["status"] == "timeout"
    assert result["error_code"] == "timeout"
