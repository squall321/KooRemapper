"""Lightweight in-memory sliding-window rate limiter (no external deps).

Single-process (the API runs as one uvicorn worker), so a process-local dict is
sufficient. Use as a FastAPI dependency: `Depends(rate_limit("login", n_per_min))`.
On limit, raises 429 with Retry-After. Disabled via KOORM_RATELIMIT_ENABLED=false.
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.shared.auth import bearer_scheme

_WINDOW = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)

# Only requests whose *direct* TCP peer is one of these are allowed to carry a
# trusted X-Forwarded-For. In this deployment nginx shares the host net
# namespace and connects to the API over loopback, so the proxy peer is always
# loopback. A request arriving from any other peer is hitting the API directly,
# so its XFF is attacker-supplied and must be ignored.
_TRUSTED_PROXY_PEERS = {"127.0.0.1", "::1", "localhost"}


def _client_key(request: Request, creds: HTTPAuthorizationCredentials | None, bucket: str) -> str:
    # Prefer the token (per-user) when present, else the client IP. Hash the FULL
    # token — a JWT's first chars are the header, identical across all users, so a
    # prefix would collapse every JWT (web) user into one shared bucket.
    if creds and creds.credentials:
        digest = hashlib.sha256(creds.credentials.encode()).hexdigest()[:24]
        return f"{bucket}:{digest}"

    peer = request.client.host if request.client else None
    xff = request.headers.get("x-forwarded-for")
    # Trust XFF only when the request actually came through our proxy, and then
    # use the LAST hop — the address nginx itself observed and appended via
    # $proxy_add_x_forwarded_for. The first hop is client-controlled (the client
    # can prepend anything) and must never be used, or rate limiting on the
    # unauthenticated endpoints (login/signup) is trivially bypassed.
    if xff and peer in _TRUSTED_PROXY_PEERS:
        ident = xff.split(",")[-1].strip() or peer
    else:
        ident = peer or "anon"
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
