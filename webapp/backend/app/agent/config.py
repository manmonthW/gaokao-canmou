"""Agent 专属配置：仅从环境变量读取，禁止硬编码凭证。

沿用 app.config 的风格：os.environ.get + 生产 fail-closed（raise RuntimeError）。
EricAI 连接参数与 Phase 0.3 探针一致；secret 只从挂载文件路径读取，值不进配置/日志。
"""
import os

# ---- 总开关（§16 Gate 0：邀请制内测）----
# 默认关闭：Agent 入口放在功能开关 + 登录白名单之后，公开页面不暴露。
AGENT_ENABLED = os.environ.get("AGENT_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")

# ---- 模型提供方（§5.2 可替换）----
# 业务代码只拿 BaseChatModel；本批只实现 ericai，其余（deepseek/qwen）预留分支。
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ericai").strip().lower()

# ---- EricAI（Azure OpenAI 兼容网关）连接参数：均从 env（与 Phase 0.3 探针一致）----
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "se-gpt-5.6-sol").strip()
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview").strip()

# Service Principal（client_credentials）——secret 只读文件路径，值绝不进配置/日志。
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "").strip()
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "").strip()
AZURE_CLIENT_SECRET_FILE = os.environ.get(
    "AZURE_CLIENT_SECRET_FILE", "/run/secrets/azure-client-secret"
).strip()

# token scope（Phase 0.3 已验证）
AZURE_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

# ---- Agent 任务库（与 USER_DB_PATH 同目录，任务/事件/审计独立存储）----
_DEFAULT_AGENT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "agent.db"
)
AGENT_DB_PATH = os.environ.get("AGENT_DB_PATH", _DEFAULT_AGENT_DB)

# ---- 邀请制、任务容量与保留策略 ----
# allowlist 支持用户 ID、邮箱或用户名，逗号分隔；空列表表示无人可用，不能误开放。
AGENT_ALLOWLIST = {
    item.strip().lower()
    for item in os.environ.get("AGENT_ALLOWLIST", "").split(",")
    if item.strip()
}
AGENT_MAX_CONCURRENCY = max(1, int(os.environ.get("AGENT_MAX_CONCURRENCY", "4")))
AGENT_USER_HOURLY_LIMIT = max(1, int(os.environ.get("AGENT_USER_HOURLY_LIMIT", "30")))
AGENT_JOB_TIMEOUT_SECONDS = max(5, int(os.environ.get("AGENT_JOB_TIMEOUT_SECONDS", "60")))
AGENT_DAILY_TOKEN_BUDGET = max(0, int(os.environ.get("AGENT_DAILY_TOKEN_BUDGET", "200000")))
AGENT_JOB_RETENTION_HOURS = max(1, int(os.environ.get("AGENT_JOB_RETENTION_HOURS", "24")))
AGENT_TRACE_RETENTION_DAYS = max(1, int(os.environ.get("AGENT_TRACE_RETENTION_DAYS", "30")))

# ---- 生产 fail-closed：只有当生产环境且 Agent 开启时才强校验连接参数 ----
# （与 app.config 的 JWT/CORS 校验同风格；开发环境不阻塞，仅在真正调用时才需要凭证）
from app.config import IS_PRODUCTION  # noqa: E402  复用同一判定

if IS_PRODUCTION and AGENT_ENABLED and LLM_PROVIDER == "ericai":
    _missing = [
        name
        for name, val in (
            ("AZURE_OPENAI_ENDPOINT", AZURE_OPENAI_ENDPOINT),
            ("AZURE_TENANT_ID", AZURE_TENANT_ID),
            ("AZURE_CLIENT_ID", AZURE_CLIENT_ID),
            ("AZURE_CLIENT_SECRET_FILE", AZURE_CLIENT_SECRET_FILE),
        )
        if not val
    ]
    if _missing:
        raise RuntimeError(
            "生产环境已开启 AGENT_ENABLED 且 LLM_PROVIDER=ericai，但缺少必需连接参数："
            + "、".join(_missing)
            + "。请在部署环境注入（secret 以只读文件挂载，值不写入配置）。"
        )
