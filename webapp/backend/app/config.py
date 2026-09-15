"""后端配置：仅从环境变量/.env 读取，禁止硬编码生产凭证。"""
import os
import warnings
from dotenv import load_dotenv

load_dotenv()

DSN = os.environ.get("GAOKAO_DSN")
if not DSN:
    raise RuntimeError(
        "GAOKAO_DSN 未设置：请在 backend/.env 中配置只读连接串 "
        "(postgresql://gaokao_web_ro:***@localhost:5432/gaokao)，"
        "不要硬编码写库(gaokao 拥有者)口令。"
    )

# 接口级安全：最大返回行数，防止批量抓取拖垮服务
MAX_PAGE_SIZE = int(os.environ.get("MAX_PAGE_SIZE", "500"))
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "*").split(",")
    if o.strip()
]
if IS_PRODUCTION and (not CORS_ORIGINS or "*" in CORS_ORIGINS):
    raise RuntimeError("生产环境 CORS_ORIGINS 必须配置为明确的 HTTPS Origin，不能使用 *。")

# ---- 用户认证（独立 SQLite 用户库，与只读分析库物理隔离）----
# 用户数据库文件路径：默认 backend/data/users.db
_DEFAULT_USER_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "users.db"
)
USER_DB_PATH = os.environ.get("USER_DB_PATH", _DEFAULT_USER_DB)

# JWT 密钥：生产必须通过环境变量注入；开发环境未设置时使用占位符并告警。
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "168"))  # 默认 7 天
_WEAK_JWT_SECRETS = {None, "", "dev-insecure-secret-change-me", "replace-this-in-production", "CHANGE_ME_TO_RANDOM_SECRET"}
if IS_PRODUCTION and (JWT_SECRET in _WEAK_JWT_SECRETS or len(JWT_SECRET or "") < 32):
    raise RuntimeError("生产环境 JWT_SECRET 必须是至少 32 字符的强随机密钥。")
if not JWT_SECRET:
    JWT_SECRET = "dev-insecure-secret-change-me"
    warnings.warn(
        "JWT_SECRET 未设置，正在使用开发占位密钥。生产环境必须在 .env 中设置 JWT_SECRET。",
        RuntimeWarning,
    )
