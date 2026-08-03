"""认证服务：bcrypt 密码哈希 + JWT 签发/校验。

安全要点：
  - 密码只存 bcrypt 哈希，永不明文；
  - JWT 密钥从环境变量注入（app.config.JWT_SECRET）；
  - 登录失败不区分“用户不存在/密码错误”，避免账号枚举。
已知 MVP 缺口（上线前需补）：登录接口无限流/防爆破。
"""
import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import user_db
from app.config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])


async def current_user(
    cred: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """FastAPI 依赖：解析 Bearer token，返回用户行；失败抛 401。"""
    if cred is None or not cred.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    try:
        uid = decode_token(cred.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的登录凭证")
    user = await user_db.get_user_by_id(uid)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user
