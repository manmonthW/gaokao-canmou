"""认证与用户数据路由。

  POST /auth/register  邮箱+用户名+密码注册
  POST /auth/login     邮箱或用户名 + 密码登录，返回 JWT
  GET  /auth/me        当前登录用户
  GET  /user/data      读取用户数据（考生档案+收藏+方案 JSON）
  PUT  /user/data      保存用户数据
"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app import user_db
from app.services import auth as auth_svc

router = APIRouter(tags=["auth"])


# ---------------- 请求/响应模型 ----------------

class RegisterReq(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _username_charset(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("用户名不能为空")
        # 允许中英文、数字、下划线、连字符
        for ch in v:
            if not (ch.isalnum() or ch in "_-"):
                raise ValueError("用户名仅允许字母、数字、中文、下划线和连字符")
        return v


class LoginReq(BaseModel):
    login: str = Field(description="邮箱或用户名")
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str


class TokenOut(BaseModel):
    token: str
    user: UserOut


class UserDataReq(BaseModel):
    data: dict


# ---------------- 路由 ----------------

@router.post("/auth/register", response_model=TokenOut)
async def register(req: RegisterReq):
    email = req.email.lower()
    if await user_db.email_exists(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    if await user_db.username_exists(req.username):
        raise HTTPException(status.HTTP_409_CONFLICT, "该用户名已被占用")
    pw_hash = auth_svc.hash_password(req.password)
    try:
        uid = await user_db.create_user(email, req.username, pw_hash)
    except Exception:
        # 并发下唯一约束兜底
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱或用户名已存在")
    token = auth_svc.create_token(uid)
    return TokenOut(token=token, user=UserOut(id=uid, email=email, username=req.username))


@router.post("/auth/login", response_model=TokenOut)
async def login(req: LoginReq):
    user = await user_db.get_user_by_login(req.login.strip())
    # 统一错误信息，避免账号枚举
    if user is None or not auth_svc.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱/用户名或密码错误")
    await user_db.touch_login(user["id"])
    token = auth_svc.create_token(user["id"])
    return TokenOut(
        token=token,
        user=UserOut(id=user["id"], email=user["email"], username=user["username"]),
    )


@router.get("/auth/me", response_model=UserOut)
async def me(user=Depends(auth_svc.current_user)):
    return UserOut(id=user["id"], email=user["email"], username=user["username"])


@router.get("/user/data")
async def get_user_data(user=Depends(auth_svc.current_user)):
    raw = await user_db.get_data(user["id"])
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = {}
    return {"data": data}


@router.put("/user/data")
async def put_user_data(req: UserDataReq, user=Depends(auth_svc.current_user)):
    await user_db.set_data(user["id"], json.dumps(req.data, ensure_ascii=False))
    return {"ok": True}
