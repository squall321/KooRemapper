"""Request authentication — resolves the current user from a JWT or a PAT.

Authorization: Bearer <token>
  - token starting with `kr_`  -> Personal Access Token (MCP / external clients)
  - otherwise                  -> JWT issued by /api/v1/auth/login (frontend)

Both resolve to a `User`. PATs are matched by sha256 hash and checked for
revocation / expiry; last_used_at is touched at most every 10 minutes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PersonalAccessToken, User
from app.shared.security import PAT_PREFIX, decode_access_token, hash_pat

bearer_scheme = HTTPBearer(auto_error=False)

_TOUCH_INTERVAL = timedelta(minutes=10)


async def _resolve_pat(db: AsyncSession, plaintext: str) -> Optional[User]:
    row = (
        await db.execute(
            select(PersonalAccessToken).where(
                PersonalAccessToken.token_hash == hash_pat(plaintext)
            )
        )
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    now = datetime.now(timezone.utc)
    if row.expires_at is not None and row.expires_at <= now:
        return None
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    # Touch last_used_at at most every 10 min, via a targeted UPDATE (no
    # read-modify-write race when the same token is used concurrently).
    if row.last_used_at is None or (now - row.last_used_at) > _TOUCH_INTERVAL:
        await db.execute(
            update(PersonalAccessToken)
            .where(PersonalAccessToken.id == row.id)
            .values(last_used_at=now)
        )
        await db.commit()
    return user


async def _resolve_jwt(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "토큰이 유효하지 않거나 만료되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰의 사용자 식별자가 잘못되었습니다.")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없거나 비활성입니다.")
    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "인증 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    if token.startswith(PAT_PREFIX):
        user = await _resolve_pat(db, token)
        if user is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "토큰이 유효하지 않거나 취소·만료되었습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    return await _resolve_jwt(db, token)


async def require_system_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_system_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "시스템 관리자 권한이 필요합니다.")
    return user
