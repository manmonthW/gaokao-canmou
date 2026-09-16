"""模型工厂单测：不走网络、不取真实 token。

只验证 make_model 构造参正确：base_url 拼接、node 参映射、minimal 被拒、
provider 切换 raise。用 monkeypatch 避免真拿 token。
"""
import asyncio

import httpx
import pytest

from app.agent import config as agent_cfg
from app.agent import llm


@pytest.fixture
def ericai_env(monkeypatch):
    """伪造一份可用的 ericai 连接配置（不碰真实网关）。"""
    monkeypatch.setattr(agent_cfg, "LLM_PROVIDER", "ericai")
    monkeypatch.setattr(agent_cfg, "AZURE_OPENAI_ENDPOINT", "https://gw.example.com")
    monkeypatch.setattr(agent_cfg, "AZURE_OPENAI_DEPLOYMENT", "se-gpt-5.6-sol")
    monkeypatch.setattr(agent_cfg, "AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    # llm 模块内也引了 agent_cfg，同一对象，patch 生效


def test_make_model_ericai_construction(ericai_env):
    m = llm.make_model(node="single_read")
    # base_url 拼到 /chat/completions
    assert str(m.openai_api_base).rstrip("/").endswith(
        "/openai/deployments/se-gpt-5.6-sol/chat/completions"
    )
    # api-version 在 default_query
    assert m.default_query.get("api-version") == "2024-12-01-preview"
    # 单条解读为生成节点，reasoning=low
    assert m.reasoning_effort == "low"


def test_tool_node_forces_reasoning_none(ericai_env):
    for node in ("tool_loop", "intent"):
        m = llm.make_model(node=node)
        assert m.reasoning_effort == "none"


def test_unknown_node_raises(ericai_env):
    with pytest.raises(ValueError):
        llm.make_model(node="nonexistent_node")


def test_provider_switch_not_implemented(monkeypatch):
    monkeypatch.setattr(agent_cfg, "LLM_PROVIDER", "deepseek")
    with pytest.raises(NotImplementedError):
        llm.make_model(node="single_read")


def test_minimal_reasoning_rejected(ericai_env, monkeypatch):
    # 人为注入一个带 minimal 的节点，验证工厂拒绝
    monkeypatch.setitem(
        llm._NODE_PARAMS,
        "bad_minimal",
        {"reasoning": "minimal", "max_completion_tokens": 100, "timeout": 10},
    )
    with pytest.raises(ValueError):
        llm.make_model(node="bad_minimal")


def test_token_provider_reads_secret_from_file(tmp_path, monkeypatch):
    """secret 只从文件读；_read_secret 返回去空白后的内容。"""
    secret_file = tmp_path / "azure-client-secret"
    secret_file.write_text("  s3cr3t-value\n", encoding="utf-8")
    monkeypatch.setattr(agent_cfg, "AZURE_CLIENT_SECRET_FILE", str(secret_file))
    provider = llm.TokenProvider()
    assert provider._read_secret() == "s3cr3t-value"


def test_token_provider_caches_token(monkeypatch):
    """get_token 缓存：同一有效期内不重复向 credential 取。"""
    import time as _time

    provider = llm.TokenProvider()
    calls = {"n": 0}

    class _FakeAccess:
        def __init__(self):
            self.token = "tok-abc"
            self.expires_on = _time.time() + 3600

    class _FakeCred:
        def get_token(self, scope):
            calls["n"] += 1
            return _FakeAccess()

    provider._credential = _FakeCred()

    async def _run():
        t1 = await provider.get_token()
        t2 = await provider.get_token()
        return t1, t2

    t1, t2 = asyncio.run(_run())
    assert t1 == t2 == "tok-abc"
    assert calls["n"] == 1


def test_auth_flow_injects_bearer(monkeypatch):
    """_Auth.async_auth_flow 注入 Authorization: Bearer。"""

    class _StubProvider:
        async def get_token(self):
            return "tok-xyz"

    async def _run():
        auth = llm._Auth(_StubProvider())
        request = httpx.Request("POST", "https://gw.example.com/x")
        gen = auth.async_auth_flow(request)
        sent = await gen.__anext__()
        assert sent.headers["Authorization"] == "Bearer tok-xyz"
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    asyncio.run(_run())
