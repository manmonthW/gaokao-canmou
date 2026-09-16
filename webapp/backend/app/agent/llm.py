"""模型工厂：产出 LangChain BaseChatModel，业务代码不感知提供方（§5.2）。

固化 Phase 0.3 已验证的接法：ChatOpenAI + httpx.Auth 连 EricAI GPT-5.6。
Token 由 Service Principal（client_credentials）获取，secret 只从挂载文件读，进程内缓存、
提前 120s 刷新，asyncio.Lock 防并发刷新。

5.6 规则（§5.3）内建：
  • 绝不传 reasoning_effort="minimal"；
  • 带 tools 的节点强制 reasoning_effort="none"（tools 与 reasoning 不能共存）；
  • 只用 max_completion_tokens（不用 max_tokens）。
"""
import asyncio
import time
from typing import Optional

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.agent import config as agent_cfg

# ---- 节点参数表（§5.3）：本批支持六个 key ----
# reasoning: None 表示不传 reasoning_effort；"none"/"low"/"medium" 按需传。
# 带工具的节点（tool_loop/intent）强制 "none"；其余为生成节点。
_NODE_PARAMS = {
    # 工具循环：带 tools → reasoning 必须 none
    "tool_loop": {"reasoning": "none", "max_completion_tokens": 2000, "timeout": 30},
    # 意图路由：带 tools → reasoning 必须 none
    "intent": {"reasoning": "none", "max_completion_tokens": 800, "timeout": 20},
    # 综合回答：生成节点（体检 medium，默认 low）
    "synthesize": {"reasoning": "low", "max_completion_tokens": 6000, "timeout": 60},
    # 修复重写：生成节点
    "repair": {"reasoning": "low", "max_completion_tokens": 6000, "timeout": 60},
    # 单条解读：生成节点
    "single_read": {"reasoning": "low", "max_completion_tokens": 3000, "timeout": 40},
    # 政策问答：生成节点
    "policy_qa": {"reasoning": "low", "max_completion_tokens": 4000, "timeout": 40},
}


class TokenProvider:
    """Service Principal token 提供器：进程内缓存 + 提前刷新 + 并发锁。

    secret 只从 AZURE_CLIENT_SECRET_FILE 指向的文件读取，值不打印、不进日志。
    """

    _REFRESH_SKEW = 120  # 提前 120s 刷新

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()
        self._credential = None  # 延迟初始化（避免 import 时就要求环境）

    def _read_secret(self) -> str:
        with open(agent_cfg.AZURE_CLIENT_SECRET_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _ensure_credential(self):
        if self._credential is None:
            # 延迟导入：只在真正取 token 时才依赖 azure-identity
            from azure.identity import ClientSecretCredential

            self._credential = ClientSecretCredential(
                tenant_id=agent_cfg.AZURE_TENANT_ID,
                client_id=agent_cfg.AZURE_CLIENT_ID,
                client_secret=self._read_secret(),
            )
        return self._credential

    async def get_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - self._REFRESH_SKEW:
            return self._token
        async with self._lock:
            # 双重检查：可能已被其他协程刷新
            now = time.time()
            if self._token and now < self._expires_at - self._REFRESH_SKEW:
                return self._token
            cred = self._ensure_credential()
            # ClientSecretCredential.get_token 是同步 IO，放线程池避免阻塞事件循环
            access = await asyncio.to_thread(cred.get_token, agent_cfg.AZURE_TOKEN_SCOPE)
            self._token = access.token
            self._expires_at = float(access.expires_on)
            return self._token


# 进程内单例 token 提供器
_token_provider = TokenProvider()


class _Auth(httpx.Auth):
    """httpx 认证钩子：每次请求注入 Authorization: Bearer <token>。"""

    def __init__(self, provider: TokenProvider) -> None:
        self._provider = provider

    async def async_auth_flow(self, request):
        token = await self._provider.get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


def make_model(*, node: str) -> BaseChatModel:
    """按节点参数表构造 BaseChatModel。

    node 必须是 _NODE_PARAMS 中的 key。Provider 非 ericai 时现阶段 raise NotImplementedError（留路）。
    """
    if node not in _NODE_PARAMS:
        raise ValueError(f"未知节点参数 key: {node!r}（可选: {sorted(_NODE_PARAMS)}）")

    if agent_cfg.LLM_PROVIDER != "ericai":
        # deepseek/qwen 等国内已备案模型预留分支，下一批再实现
        raise NotImplementedError(
            f"LLM_PROVIDER={agent_cfg.LLM_PROVIDER!r} 尚未实现；本批只支持 ericai。"
        )

    params = _NODE_PARAMS[node]
    endpoint = agent_cfg.AZURE_OPENAI_ENDPOINT
    deployment = agent_cfg.AZURE_OPENAI_DEPLOYMENT
    version = agent_cfg.AZURE_OPENAI_API_VERSION

    # base_url 拼到 /chat/completions（Phase 0.3 实测网关容忍）
    base_url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"

    http_client = httpx.AsyncClient(auth=_Auth(_token_provider))

    kwargs = dict(
        model=deployment,
        api_key="managed-by-http-auth",  # 真实凭证由 httpx.Auth 注入，此值仅占位
        base_url=base_url,
        default_query={"api-version": version},
        default_headers={"User-Agent": "curl/8.5.0", "Accept": "application/json"},
        http_async_client=http_client,
        max_completion_tokens=params["max_completion_tokens"],
        timeout=params["timeout"],
        max_retries=1,
    )

    # 5.6 规则：绝不传 minimal；只有非 None 才传 reasoning_effort
    reasoning = params["reasoning"]
    if reasoning == "minimal":
        raise ValueError("5.6 禁止 reasoning_effort='minimal'（§5.3）。")
    if reasoning is not None:
        kwargs["reasoning_effort"] = reasoning

    return ChatOpenAI(**kwargs)
