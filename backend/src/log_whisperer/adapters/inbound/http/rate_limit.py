"""Sliding-window rate limit per client IP, applied before the body is read."""

import json
import time
from collections import deque
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

WINDOW_SECONDS = 60.0
LIMITED_PREFIX = "/api/"


class SlidingWindowLimiter:
    def __init__(
        self,
        limit: int,
        window: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._last_sweep = clock()

    @property
    def tracked_clients(self) -> int:
        return len(self._hits)

    def allow(self, client: str) -> bool:
        now = self._clock()
        cutoff = now - self._window
        if now - self._last_sweep >= self._window:
            self._evict_idle(cutoff)
            self._last_sweep = now
        hits = self._hits.setdefault(client, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True

    def _evict_idle(self, cutoff: float) -> None:
        idle = [client for client, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for client in idle:
            del self._hits[client]


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limiter: SlidingWindowLimiter) -> None:
        self._app = app
        self._limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(LIMITED_PREFIX):
            await self._app(scope, receive, send)
            return
        client = scope.get("client")
        host = client[0] if client else "unknown"
        if self._limiter.allow(host):
            await self._app(scope, receive, send)
            return
        await send_error(send, 429, "Rate limit exceeded")


async def send_error(send: Send, status: int, message: str) -> None:
    body = json.dumps({"error": message}).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
