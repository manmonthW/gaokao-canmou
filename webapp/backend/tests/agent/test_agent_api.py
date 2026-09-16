import asyncio
from types import SimpleNamespace

import pytest
import httpx
from fastapi import HTTPException

from app.agent import config
from app.routers import agent


USER = {"id": 7, "email": "invite@example.com", "username": "invitee"}


def test_authorized_requires_switch_and_allowlist(monkeypatch):
    monkeypatch.setattr(config, "AGENT_ENABLED", False)
    with pytest.raises(HTTPException) as exc:
        agent._authorized(USER)
    assert exc.value.status_code == 503

    monkeypatch.setattr(config, "AGENT_ENABLED", True)
    monkeypatch.setattr(config, "AGENT_ALLOWLIST", {"someone-else"})
    with pytest.raises(HTTPException) as exc:
        agent._authorized(USER)
    assert exc.value.status_code == 403

    monkeypatch.setattr(config, "AGENT_ALLOWLIST", {"invite@example.com"})
    assert agent._authorized(USER) == USER


def test_create_reuses_active_job(monkeypatch):
    async def fake_admission(user_id):
        return "active", {"id": "existing", "status": "running"}

    monkeypatch.setattr(agent.jobs, "admission", fake_admission)
    req = agent.CreateJobRequest(message="推荐几个学校")
    result = asyncio.run(agent.create_job(req, USER))
    assert result == {"job_id": "existing", "status": "running", "reused": True}


def test_create_starts_new_job(monkeypatch):
    async def fake_admission(user_id):
        return "ok", None

    async def fake_create(user_id, payload):
        assert payload["message"] == "推荐几个学校"
        return {"id": "new", "status": "pending"}

    monkeypatch.setattr(agent.jobs, "admission", fake_admission)
    monkeypatch.setattr(agent.jobs, "create", fake_create)
    result = asyncio.run(agent.create_job(agent.CreateJobRequest(message="推荐几个学校"), USER))
    assert result["job_id"] == "new"
    assert result["reused"] is False


def test_get_cancel_feedback_not_found(monkeypatch):
    async def none(*args, **kwargs):
        return None

    monkeypatch.setattr(agent.jobs, "get", none)
    monkeypatch.setattr(agent.jobs, "cancel", none)
    monkeypatch.setattr(agent.jobs, "feedback", none)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(agent.get_job("missing", user=USER))
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        asyncio.run(agent.cancel_job("missing", user=USER))
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        asyncio.run(agent.give_feedback("missing", agent.FeedbackRequest(helpful=True), USER))
    assert exc.value.status_code == 404


def test_request_contract_limits_history_and_message():
    with pytest.raises(ValueError):
        agent.CreateJobRequest(message=" ")
    turns = [agent.HistoryTurn(role="user", content="x") for _ in range(7)]
    with pytest.raises(ValueError):
        agent.CreateJobRequest(message="x", history=turns)


def test_agent_routes_are_reachable_through_asgi():
    from app.main import app

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/agent/jobs", json={"message": "推荐几个学校"})

    response = asyncio.run(request())
    assert response.status_code == 401
    assert response.json()["detail"] == "未登录"
