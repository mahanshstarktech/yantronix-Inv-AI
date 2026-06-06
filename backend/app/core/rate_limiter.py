"""Small in-memory fixed-window rate limiter.

The limiter is intentionally dependency-free. It protects the local FastAPI
process from accidental spam and expensive AI calls. In a multi-instance
production deployment, replace this class with a Redis-backed implementation
that preserves the same `check` method contract.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, DefaultDict

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class LimitPolicy:
    """Configuration for a single rate-limit bucket."""

    name: str
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Thread-safe sliding-window limiter keyed by caller and action."""

    def __init__(self) -> None:
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, policy: LimitPolicy) -> None:
        """Record one hit or raise HTTP 429 when the policy is exceeded."""

        now = time.time()
        bucket_key = f"{policy.name}:{key}"
        with self._lock:
            hits = self._hits[bucket_key]
            while hits and hits[0] <= now - policy.window_seconds:
                hits.popleft()
            if len(hits) >= policy.max_requests:
                retry_after = max(1, int(policy.window_seconds - (now - hits[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Rate limit exceeded for {policy.name}. "
                        f"Try again in {retry_after} seconds."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


def client_key(request: Request) -> str:
    """Return a stable caller key using forwarded IP when available."""

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


rate_limiter = InMemoryRateLimiter()
