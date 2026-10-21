"""可写库连接（用户库 + Agent 任务库）：SQLite 或 PostgreSQL 二选一。

- 未设置 APP_DB_URL：沿用 SQLite 单文件（EWS 容器 / 本地开发 / 单测）。
- 设置 APP_DB_URL：走 PostgreSQL（Vercel 等无持久磁盘的平台；如 Neon 的 pooled 连接串）。
  与只读分析库（GAOKAO_DSN / gaokao_web_ro）用不同角色、不同连接，二者不混用。

业务 SQL 统一写成 SQLite 风格的 `?` 占位符，PG 模式下转换为 `%s`；
时间统一由 Python 生成 UTC 文本（见 now_text/cutoff_text），不依赖方言函数。
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

APP_DB_URL = os.environ.get("APP_DB_URL", "").strip()
IS_PG = bool(APP_DB_URL)

_PG_POOL_MAX = max(1, int(os.environ.get("APP_DB_POOL_MAX", "3")))
_POOL_WAIT_SECONDS = float(os.environ.get("DB_POOL_WAIT_SECONDS", "10"))
_IDLE_CHECK_SECONDS = 60
_pg_pool = None
_pg_pool_lock = threading.Lock()


def make_blocking_pool(maxconn: int, dsn: str):
    """psycopg2 连接池的两处补丁，Serverless + Neon 下都必需：

    1. ThreadedConnectionPool 用满时会立即抛 PoolError；小池（2–3 连接）下并发请求很容易撞上。
       用信号量让 getconn 排队，最多等 DB_POOL_WAIT_SECONDS 秒。
    2. Neon 空闲会挂起、函数实例会被冻结，池里的连接可能已被服务端断开而客户端不知道。
       空闲超过 60 秒的连接取出前先 SELECT 1，失败就丢弃重连。
    """
    import time

    from psycopg2 import pool

    class _BlockingPool(pool.ThreadedConnectionPool):
        def __init__(self):
            self._slots = threading.BoundedSemaphore(maxconn)
            self._last_used: dict[int, float] = {}
            super().__init__(1, maxconn, dsn)

        def _alive(self, conn) -> bool:
            if conn.closed:
                return False
            if time.monotonic() - self._last_used.get(id(conn), 0) < _IDLE_CHECK_SECONDS:
                return True
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()
                return True
            except Exception:  # noqa: BLE001 - any failure means the connection is unusable
                return False

        def getconn(self, key=None):
            if not self._slots.acquire(timeout=_POOL_WAIT_SECONDS):
                raise pool.PoolError("数据库连接池繁忙，请稍后重试")
            try:
                for _ in range(maxconn + 1):
                    conn = super().getconn(key)
                    if self._alive(conn):
                        return conn
                    self._last_used.pop(id(conn), None)
                    super().putconn(conn, key, close=True)
                raise pool.PoolError("无法建立数据库连接")
            except Exception:
                self._slots.release()
                raise

        def putconn(self, conn, key=None, close=False):
            try:
                if close or conn.closed:
                    self._last_used.pop(id(conn), None)
                else:
                    self._last_used[id(conn)] = time.monotonic()
                super().putconn(conn, key, close=close or bool(conn.closed))
            finally:
                self._slots.release()

    return _BlockingPool()


def now_text(precise: bool = False) -> str:
    """UTC 时间文本；precise=False 与 SQLite datetime('now') 格式一致。"""
    fmt = "%Y-%m-%d %H:%M:%S.%f" if precise else "%Y-%m-%d %H:%M:%S"
    return datetime.now(timezone.utc).strftime(fmt)


def cutoff_text(**delta) -> str:
    """当前 UTC 减去 timedelta(**delta) 的时间文本，用于与存储的时间文本做字典序比较。"""
    return (datetime.now(timezone.utc) - timedelta(**delta)).strftime("%Y-%m-%d %H:%M:%S")


def start_of_day_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d 00:00:00")


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        with _pg_pool_lock:
            if _pg_pool is None:
                _pg_pool = make_blocking_pool(_PG_POOL_MAX, APP_DB_URL)
    return _pg_pool


class _PgConn:
    """给 psycopg2 连接套一层 sqlite3 风格的 execute（返回游标，行可按列名取）。"""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        from psycopg2.extras import RealDictCursor

        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql.replace("?", "%s"), tuple(params))
        return cur

    def executescript(self, script):
        with self._conn.cursor() as cur:
            cur.execute(script)


@contextmanager
def connect(sqlite_path: str):
    """事务上下文：正常退出提交，异常回滚。SQLite 模式下 sqlite_path 为库文件。"""
    if IS_PG:
        pg_pool = _get_pg_pool()
        conn = pg_pool.getconn()
        broken = False
        try:
            yield _PgConn(conn)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 - connection already dead
                broken = True
            raise
        finally:
            pg_pool.putconn(conn, close=broken or bool(conn.closed))
        return

    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    conn = sqlite3.connect(sqlite_path, timeout=10)
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


def schema_lock(conn, key: int):
    """PG 模式下串行化建表（多个实例同时冷启动时避免 CREATE IF NOT EXISTS 竞争）。"""
    if IS_PG:
        conn.execute("SELECT pg_advisory_xact_lock(?)", (key,))
