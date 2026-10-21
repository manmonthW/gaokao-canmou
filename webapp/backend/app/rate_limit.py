"""Rate limiter for expensive or abuse-prone endpoints.

- SQLite / single process (EWS): in-memory sliding window, as before.
- PostgreSQL (APP_DB_URL, Vercel): serverless instances share nothing in memory, so counts
  live in the shared writable DB as fixed one-window buckets. Slightly coarser than a
  sliding window (a burst straddling two windows can reach 2x limit), acceptable for
  brute-force protection.

Client IP comes from X-Forwarded-For's first hop. Vercel overwrites that header with the
real client address. The EWS nginx uses $proxy_add_x_forwarded_for, which *appends*, so
there the first hop is client-controlled and the limiter can be bypassed by spoofing it
(pre-existing; fix in nginx with `proxy_set_header X-Forwarded-For $remote_addr`).
"""
import asyncio
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app import sqlstore

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_limit_hits (
    name         TEXT NOT NULL,
    client       TEXT NOT NULL,
    window_start BIGINT NOT NULL,
    hits         INTEGER NOT NULL,
    PRIMARY KEY (name, client, window_start)
);
"""
_pg_ready = False
_pg_lock = threading.Lock()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _pg_hit(name: str, client: str, window_seconds: int) -> int:
    global _pg_ready
    window_start = int(time.time()) // window_seconds * window_seconds
    with sqlstore.connect("") as conn:
        if not _pg_ready:
            with _pg_lock:
                if not _pg_ready:
                    sqlstore.schema_lock(conn, 7303)
                    conn.executescript(_PG_SCHEMA)
                    _pg_ready = True
        hits = conn.execute(
            "INSERT INTO rate_limit_hits (name, client, window_start, hits) VALUES (?, ?, ?, 1) "
            "ON CONFLICT (name, client, window_start) DO UPDATE SET hits = rate_limit_hits.hits + 1 "
            "RETURNING hits",
            (name, client, window_start),
        ).fetchone()["hits"]
        if hits == 1:  # 每个新窗口顺手清掉旧桶，表不会无限增长
            conn.execute(
                "DELETE FROM rate_limit_hits WHERE name = ? AND window_start < ?",
                (name, window_start - window_seconds),
            )
        return hits


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int, name: str = "default"):
        self.limit = limit
        self.window_seconds = window_seconds
        self.name = name
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, request: Request):
        key = _client_key(request)
        if sqlstore.IS_PG:
            hits = await run_in_threadpool(_pg_hit, self.name, key, self.window_seconds)
            if hits > self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试")
            return
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试")
            hits.append(now)


auth_limiter = SlidingWindowLimiter(limit=10, window_seconds=60, name="auth")
