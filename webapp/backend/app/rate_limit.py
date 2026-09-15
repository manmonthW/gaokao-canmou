"""Small in-process rate limiter for expensive or abuse-prone endpoints."""
import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, request: Request):
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        key = forwarded or (request.client.host if request.client else "unknown")
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试")
            hits.append(now)


auth_limiter = SlidingWindowLimiter(limit=10, window_seconds=60)
