"""Lightweight in-memory sliding-window rate limiter (no external deps).

Single-process (the API runs as one uvicorn worker), so a process-local dict is
sufficient. Use as a FastAPI dependency: `Depends(rate_limit("login", n_per_min))`.
On limit, raises 429 with Retry-After. Disabled via KOORM_RATELIMIT_ENABLED=false.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.shared.auth import bearer_scheme

_WINDOW = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, creds: HTTPAuthorizationCredentials | None, bucket: str) -> str:
    # Prefer the token (per-user) when present, else client IP.
    if creds and creds.credentials:
        ident = creds.credentials[:24]
    else:
        ident = request.client.host if request.client else "anon"
    return f"{bucket}:{ident}"


def rate_limit(bucket: str, per_min: int):
    """Dependency factory. `per_min` requests allowed per 60s sliding window."""

    async def _dep(
        request: Request,
        creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        if not settings.ratelimit_enabled or per_min <= 0:
            return
        key = _client_key(request, creds, bucket)
        now = time.monotonic()
        dq = _hits[key]
        cutoff = now - _WINDOW
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= per_min:
            retry = max(1, int(_WINDOW - (now - dq[0])))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"요청이 너무 많습니다. {retry}초 후 다시 시도하세요. (한도 {per_min}/분)",
                headers={"Retry-After": str(retry), "X-RateLimit-Limit": str(per_min)},
            )
        dq.append(now)

    return _dep
