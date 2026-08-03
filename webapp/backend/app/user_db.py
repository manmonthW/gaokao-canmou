"""用户数据库（SQLite，与只读 PostgreSQL 分析库物理隔离）。

MVP 最轻量：单文件 SQLite，标准库 sqlite3，无额外基础设施。
仅存放用户账户（邮箱/用户名/密码哈希）与用户数据快照（考生档案+收藏+方案，JSON）。
分析数据仍走只读的 gaokao_web_ro（app/db.py），二者不混用连接。

线程安全：每次操作新建连接（sqlite3 连接不可跨线程共享），
写入量低，FastAPI 通过 run_in_threadpool 调用，性能足够。
"""
import os
import sqlite3
from contextlib import contextmanager

from fastapi.concurrency import run_in_threadpool

from app.config import USER_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS user_data (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data       TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- 唯一性大小写不敏感（避免 A@x.com 与 a@x.com 重复注册）
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users(lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower ON users(lower(username));
"""


def init_db():
    """建库建表（幂等）。由 lifespan 启动时调用。"""
    os.makedirs(os.path.dirname(USER_DB_PATH), exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect():
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- 同步实现 ----------------

def _create_user(email, username, password_hash):
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
            (email, username, password_hash),
        )
        uid = cur.lastrowid
        conn.execute("INSERT INTO user_data (user_id, data) VALUES (?, '{}')", (uid,))
        return uid


def _get_user_by_login(login):
    """按 email 或 username（大小写不敏感）取用户。"""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?) OR lower(username)=lower(?)",
            (login, login),
        ).fetchone()


def _get_user_by_id(uid):
    with _connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def _email_exists(email):
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE lower(email)=lower(?)", (email,)
        ).fetchone() is not None


def _username_exists(username):
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE lower(username)=lower(?)", (username,)
        ).fetchone() is not None


def _touch_login(uid):
    with _connect() as conn:
        conn.execute("UPDATE users SET last_login_at=datetime('now') WHERE id=?", (uid,))


def _get_data(uid):
    with _connect() as conn:
        row = conn.execute("SELECT data FROM user_data WHERE user_id=?", (uid,)).fetchone()
        return row["data"] if row else "{}"


def _set_data(uid, data_json):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO user_data (user_id, data, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=datetime('now')",
            (uid, data_json),
        )


# ---------------- 异步包装（供 FastAPI 调用） ----------------

async def create_user(email, username, password_hash):
    return await run_in_threadpool(_create_user, email, username, password_hash)


async def get_user_by_login(login):
    return await run_in_threadpool(_get_user_by_login, login)


async def get_user_by_id(uid):
    return await run_in_threadpool(_get_user_by_id, uid)


async def email_exists(email):
    return await run_in_threadpool(_email_exists, email)


async def username_exists(username):
    return await run_in_threadpool(_username_exists, username)


async def touch_login(uid):
    return await run_in_threadpool(_touch_login, uid)


async def get_data(uid):
    return await run_in_threadpool(_get_data, uid)


async def set_data(uid, data_json):
    return await run_in_threadpool(_set_data, uid, data_json)
