"""数据库连接池（psycopg2 同步 + FastAPI 线程池执行），Web 端仅只读。

连接池采用懒加载：首次使用时才建立（import 阶段不连库），
由 FastAPI 的 lifespan 在启动时显式 init、关闭时 closeall，
便于单测在无需真实数据库的情况下 import 本模块。
"""
import os
import threading

import psycopg2
from fastapi.concurrency import run_in_threadpool
from app.config import DSN
from app.sqlstore import make_blocking_pool

_pool = None
_pool_lock = threading.Lock()
# 常驻容器（EWS）默认 12；Serverless（Vercel）每个实例一个池，应设 2–3，并配合 Neon 的 -pooler 连接串。
# 池满时排队等待（见 sqlstore.make_blocking_pool），不会直接报错。
_MAX_CONN = max(1, int(os.environ.get("GAOKAO_DB_POOL_MAX", "12")))


def init_pool():
    """显式初始化连接池（由 lifespan 调用）。"""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = make_blocking_pool(_MAX_CONN, DSN)


def close_pool():
    """关闭连接池并释放所有连接（由 lifespan 调用）。"""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def get_pool():
    """获取连接池，懒加载兜底（防止 lifespan 未触发时仍可用）。"""
    if _pool is None:
        init_pool()
    return _pool


def _execute(query, params=None, fetch="all"):
    conn = get_pool().getconn()
    try:
        with conn:  # 自动提交 / 异常回滚
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch == "none":
                    return None
                if fetch == "one":
                    return cur.fetchone()
                return cur.fetchall()
    finally:
        get_pool().putconn(conn)


async def fetch_all(query, params=None):
    return await run_in_threadpool(_execute, query, params, "all")


async def fetch_one(query, params=None):
    return await run_in_threadpool(_execute, query, params, "one")


def schema_missing(exc: Exception) -> bool:
    """判断异常是否为「旧库未迁移」类模式缺失。

    _execute 原样透传 psycopg2 异常；UndefinedTable（42P01）与
    UndefinedColumn（42703）表示目标表/列尚未经 migration 建立，
    服务层可据此降级为新功能隐身（返回空数据），其余错误照常抛出。
    """
    return getattr(exc, "pgcode", None) in ("42P01", "42703")
